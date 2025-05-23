import os
import json
import urllib.request
import pymysql
import re
from datetime import datetime
# import boto3
# from botocore.exceptions import ClientError

# Map Thai month names → month numbers
THAI_MONTHS = {
    "มกราคม": 1, "กุมภาพันธ์": 2, "มีนาคม": 3, "เมษายน": 4,
    "พฤษภาคม": 5, "มิถุนายน": 6, "กรกฎาคม": 7, "สิงหาคม": 8,
    "กันยายน": 9, "ตุลาคม": 10, "พฤศจิกายน": 11, "ธันวาคม": 12
}

def parse_thai_date(date_str):
    try:
        if not date_str:
            return None
        parts = re.split(r'\s+', date_str.strip())
        day = int(parts[0])
        month = THAI_MONTHS.get(parts[1], 0)
        year = int(parts[2]) - 543
        return datetime(year, month, day).date()
    except:
        return None

def parse_thai_time(time_str):
    try:
        if not time_str:
            return None
        match = re.match(r'(\d{1,2}:\d{2})', time_str)
        if match:
            return datetime.strptime(match.group(1), "%H:%M").time()
        return None
    except:
        return None

def remove_thai_honorific(name):
    if not name:
        return 'ไม่ระบุ'
    
    honorifics = ['นาย', 'นาง', 'นางสาว', 'ด.ช.', 'ด.ญ.', 'เด็กชาย', 'เด็กหญิง']
    processed_name = name.strip()
    
    for honorific in honorifics:
        if processed_name.startswith(honorific):
            processed_name = processed_name[len(honorific):].strip()
            break
    
    return processed_name or 'ไม่ระบุ'

def store_items_in_db(items):
    """Store items in the database."""
    conn = pymysql.connect(
        host="localhost",
        port=3306,
        user="admin",
        password="12345678",
        database="missing_persons_db",
        cursorclass=pymysql.cursors.DictCursor
    )
    
    try:
        with conn.cursor() as cur:
            for item in items:
                cleaned_name = remove_thai_honorific(item['full_name'])
                
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

                # Create description from available information
                description_parts = []
                if item.get('nationality'):
                    description_parts.append(f"สัญชาติ: {item['nationality']}")
                if item.get('age_missing'):
                    description_parts.append(f"อายุขณะหายตัว: {item['age_missing']} ปี")
                if item.get('age_current'):
                    description_parts.append(f"อายุปัจจุบัน: {item['age_current']} ปี")
                if item.get('gender'):
                    description_parts.append(f"เพศ: {item['gender']}")
                if item.get('missing_date'):
                    description_parts.append(f"วันที่หายตัว: {item['missing_date']}")
                if item.get('missing_time'):
                    description_parts.append(f"เวลาที่หายตัว: {item['missing_time']}")
                if item.get('missing_location'):
                    description_parts.append(f"สถานที่หายตัว: {item['missing_location']}")
                if item.get('inform_location'):
                    description_parts.append(f"สถานที่แจ้งเหตุ: {item['inform_location']}")
                
                description = "\n".join(description_parts) if description_parts else None

                # Check if this platform's information already exists
                check_platform_sql = """
                SELECT case_id FROM case_information 
                WHERE case_id = %(case_id)s AND platform = %(platform)s
                """
                cur.execute(check_platform_sql, {
                    'case_id': case_id,
                    'platform': 'thaimissing'
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
                        'platform': 'thaimissing',
                        'picture': item['photo_url'],
                        'url': item['source_url'],
                        'description': description
                    })
                    print(f"Added new case information for platform 'thaimissing' for case ID {case_id}")
                else:
                    print(f"Case information for platform 'thaimissing' already exists for case ID {case_id}, skipping...")

        conn.commit()
        print(f"Successfully stored {len(items)} items in database")
    except Exception as e:
        print(f"Database error: {e}")
        conn.rollback()
    finally:
        conn.close()

def lambda_handler():
    # --- 1) Load config ---
    api_url = "https://api.thaimissing.go.th/api/v1/cir-Datacatalog-web/DataMissingPerson"

    # --- 2) Fetch API data ---
    resp = urllib.request.urlopen(api_url)
    data = json.loads(resp.read().decode('utf-8'))

    # --- 3) Process and store data ---
    items = []
    for rec in data:
        try:
            age_missing = int("".join(re.findall(r"\d", rec.get('ageMissing'))))
        except:
            age_missing = None

        try:
            age_current = int("".join(re.findall(r"\d", rec.get('ageCurrent'))))
        except:
            age_current = None
        
        try:
            age_inform = int("".join(re.findall(r"\d", rec.get('ageInform'))))
        except:
            age_inform = None

        items.append({
            'full_name': rec.get('fullName'),
            'nationality': rec.get('nationality'),
            'age_missing': age_missing,
            'age_current': age_current,
            'age_inform': age_inform,
            'gender': rec.get('sex'),
            'missing_date': parse_thai_date(rec.get('missingDate')),
            'missing_time': parse_thai_time(rec.get('missingTime')),
            'missing_location': rec.get('missingLocation'),
            'inform_location': rec.get('informLocation'),
            'photo_url': rec.get('image'),
            'source_url': rec.get('url')
        })

    # --- 4) Store in database ---
    store_items_in_db(items)

    return {
        'statusCode': 200,
        'body': json.dumps({'processed': len(items)})
    }

if __name__ == '__main__':
    lambda_handler()