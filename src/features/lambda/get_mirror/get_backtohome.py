import time
import os
import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin, parse_qs, urlparse
from concurrent.futures import ThreadPoolExecutor
import pymysql
from datetime import datetime

BASE_URL = "https://web.backtohome.org/net%20missing.php?width=1920&height=1080&pages="

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'admin',
    'password': '12345678',
    'database': 'missing_persons_db'
}

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (compatible; MissingScraper/1.0; +https://yourdomain.com)'
})

def get_total_pages():
    """Determine the total number of pages to scrape."""
    resp = session.get(f"{BASE_URL}1#content", timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    page_numbers = {
        int(link['href'].split('pages=')[1].split('#')[0])
        for link in soup.select('a[href*="pages="]')
    }
    return max(page_numbers or {1})

def fetch_and_process_page(page):
    """Fetch a page and process all its listings."""
    url = f"{BASE_URL}{page}#content"
    resp = session.get(url, timeout=10)
    soup = BeautifulSoup(resp.content, 'html.parser')
    
    items = []
    # Process all listings on the page
    for img_div, detail_div in zip(soup.select('.miss_img'), soup.select('.miss_detail')):
        # Extract link and ID
        link_tag = img_div.find('a', href=True)
        detail_link = urljoin('https://web.backtohome.org/', link_tag['href']) if link_tag else None
        person_id = parse_qs(urlparse(detail_link).query).get('id', [None])[0] if detail_link else None
        
        # Extract image URL
        image_url = next(
            (img['src'] for img in img_div.find_all('img') 
             if not any(x in img['src'] for x in ['small_missing', 'small_childmissing'])),
            None
        )
        
        # Extract name and age
        center_texts = [d.get_text(strip=True) for d in detail_div.find_all('div', align='center')]
        name = center_texts[0] if center_texts else None
        age = center_texts[1].strip('()') if len(center_texts) > 1 else None
        
        items.append({
            'id': person_id,
            'name': name,
            'age': age,
            'detail_link': detail_link,
            'image_url': image_url
        })
    
    print(f"Page {page}: found {len(items)} listings")
    return items

def fetch_detail(item):
    """Fetch and extract details for a single item."""
    if not item.get('detail_link'):
        print(f"No detail link for item: {item.get('id')}")
        item['detail'] = None
        return item
    
    try:
        print(f"Fetching details from: {item['detail_link']}")
        resp = session.get(item['detail_link'], timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        target = soup.select_one('#content > article > div')
        if target and len(target.find_all('div', recursive=False)) >= 2:
            text = target.find_all('div', recursive=False)[1].get_text(' ', strip=True)
            # Clean up text
            text = re.sub(r'\s+', ' ', text)
            text = re.sub(r'([.!?])\s+', r'\1\n\n', text)
            text = re.sub(r'\*\*\s*', '**\n\n', text)
            text = re.sub(r'\n\s*\n', ' ', text)
            item['detail'] = text
            print(f"Found detail text for item {item.get('id')}")
        else:
            print(f"No detail content found for item {item.get('id')}")
            item['detail'] = None
    except Exception as e:
        print(f"Error fetching details for ID={item.get('id')}: {e}")
        item['detail'] = None
    
    return item

def remove_thai_honorific(name):
    if not name:
        return 'ไม่ระบุ'
    
    honorifics = ['นาย','นางสาว', 'นาง', 'ด.ช.', 'ด.ญ.', 'เด็กชาย', 'เด็กหญิง']
    processed_name = name.strip()
    
    for honorific in honorifics:
        if processed_name.startswith(honorific):
            processed_name = processed_name[len(honorific):].strip()
            break
    
    # Normalize spaces - replace multiple spaces with a single space
    processed_name = ' '.join(processed_name.split())
    
    return processed_name or 'ไม่ระบุ'

def store_items_in_db(items):
    """Store items in the database."""
    conn = pymysql.connect(
        **DB_CONFIG,
        cursorclass=pymysql.cursors.DictCursor
    )
    
    try:
        with conn.cursor() as cur:
            # Get all existing case IDs and names for this platform
            existing_cases_sql = """
            SELECT c.id, c.name 
            FROM cases c
            JOIN case_information ci ON c.id = ci.case_id
            WHERE ci.platform = 'backtohome'
            """
            cur.execute(existing_cases_sql)
            existing_cases = cur.fetchall()
            print(f"Found {len(existing_cases)} existing cases in database")
            
            # Create a set of new case names for comparison
            new_case_names = {remove_thai_honorific(item['name']) for item in items}
            print(f"Found {len(new_case_names)} new cases from source")
            
            # Find cases to mark as inactive (those that don't exist in new data)
            cases_to_mark = []
            for case in existing_cases:
                if case['name'] not in new_case_names:
                    cases_to_mark.append(case['id'])
                    print(f"Case {case['id']} with name '{case['name']}' not found in new data")
            
            print(f"Found {len(cases_to_mark)} cases to mark as inactive")
            
            # Mark cases as inactive by updating case_information
            if cases_to_mark:
                update_sql = """
                UPDATE case_information 
                SET description = CONCAT(COALESCE(description, ''), '\n[INACTIVE - No longer found in source]'),
                    created_at = NOW()
                WHERE case_id IN %(case_ids)s AND platform = 'backtohome'
                """
                cur.execute(update_sql, {'case_ids': tuple(cases_to_mark)})
                print(f"Marked {len(cases_to_mark)} old cases as inactive")
                
                # Delete marked cases from case_information
                delete_marked_sql = """
                DELETE FROM case_information 
                WHERE case_id IN %(case_ids)s AND platform = 'backtohome'
                """
                cur.execute(delete_marked_sql, {'case_ids': tuple(cases_to_mark)})
                print(f"Deleted {len(cases_to_mark)} marked cases from case_information")
                
                # Find and delete orphaned cases (cases with no case_information)
                delete_orphaned_sql = """
                DELETE FROM cases 
                WHERE id IN %(case_ids)s 
                AND NOT EXISTS (
                    SELECT 1 FROM case_information 
                    WHERE case_id = cases.id
                )
                """
                cur.execute(delete_orphaned_sql, {'case_ids': tuple(cases_to_mark)})
                print(f"Deleted orphaned cases from cases table")
            
            # Process new items
            for item in items:
                cleaned_name = remove_thai_honorific(item['name'])
                
                # Check if case with same name exists
                check_sql = """
                SELECT id FROM cases WHERE name = %(name)s
                """
                cur.execute(check_sql, {'name': cleaned_name})
                result = cur.fetchone()
                
                if result:
                    # Use existing case ID
                    case_id = result['id']
                    print(f"Found existing case with name '{cleaned_name}', using ID: {case_id}")
                else:
                    # Insert new case
                    case_sql = """
                    INSERT INTO cases (name, created_at)
                    VALUES (%(name)s, NOW())
                    """
                    cur.execute(case_sql, {'name': cleaned_name})
                    case_id = cur.lastrowid
                    print(f"Created new case with name '{cleaned_name}', ID: {case_id}")

                # Check if this platform's information already exists
                check_platform_sql = """
                SELECT case_id FROM case_information 
                WHERE case_id = %(case_id)s AND platform = %(platform)s
                """
                cur.execute(check_platform_sql, {
                    'case_id': case_id,
                    'platform': 'backtohome'
                })
                existing_platform = cur.fetchone()

                if not existing_platform:
                    # Insert new case_information row
                    info_sql = """
                    INSERT INTO case_information (
                        case_id, platform, picture, url, description, created_at
                    ) VALUES (
                        %(case_id)s, %(platform)s, %(picture)s, %(url)s, %(description)s, NOW()
                    )
                    """
                    
                    cur.execute(info_sql, {
                        'case_id': case_id,
                        'platform': 'backtohome',
                        'picture': item['image_url'],
                        'url': item['detail_link'],
                        'description': item.get('detail')
                    })
                    print(f"Added new case information for platform 'backtohome' for case ID {case_id}")
                else:
                    # Update existing case information
                    update_sql = """
                    UPDATE case_information 
                    SET picture = %(picture)s,
                        url = %(url)s,
                        description = %(description)s,
                        created_at = NOW()
                    WHERE case_id = %(case_id)s 
                    AND platform = 'backtohome'
                    AND (
                        picture != %(picture)s 
                        OR url != %(url)s 
                        OR description != %(description)s
                    )
                    """
                    cur.execute(update_sql, {
                        'case_id': case_id,
                        'platform': 'backtohome',
                        'picture': item['image_url'],
                        'url': item['detail_link'],
                        'description': item.get('detail')
                    })
                    if cur.rowcount > 0:
                        print(f"Updated existing case information for platform 'backtohome' for case ID {case_id}")
                    else:
                        print(f"No changes needed for case ID {case_id}")

        conn.commit()
        print(f"Successfully stored {len(items)} items in database")
    except Exception as e:
        print(f"Database error: {e}")
        conn.rollback()
    finally:
        conn.close()

def main():
    start_time = time.time()
    total_pages = get_total_pages()
    print(f"Total pages to process: {total_pages}")
    
    # First, collect all items from all pages
    all_items = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        page_items = list(executor.map(fetch_and_process_page, range(1, total_pages + 1)))
        all_items = [item for page_items in page_items for item in page_items]
    
    print(f"Collected {len(all_items)} total items from all pages")
    
    # Then, fetch details for all items
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_detail, item): item for item in all_items}
        for future in futures:
            try:
                future.result()
            except Exception as e:
                print(f"Error processing item: {e}")
    
    # Finally, store all items in database at once
    store_items_in_db(all_items)
    
    elapsed = time.time() - start_time
    print(f"All done in {elapsed:.2f}s. Processed {len(all_items)} total items.")

if __name__ == '__main__':
    main()