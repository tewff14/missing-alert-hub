import json
import urllib.request
import pymysql
import os
import re
from datetime import datetime

# 1. Map Thai month names → month numbers
THAI_MONTHS = {
    "มกราคม":   1,
    "กุมภาพันธ์": 2,
    "มีนาคม":    3,
    "เมษายน":    4,
    "พฤษภาคม":   5,
    "มิถุนายน":   6,
    "กรกฎาคม":   7,
    "สิงหาคม":    8,
    "กันยายน":    9,
    "ตุลาคม":    10,
    "พฤศจิกายน":  11,
    "ธันวาคม":   12,
}

def parse_thai_date(thai_date_str: str) -> datetime.date:
    """
    Parse a Thai date in the form 'DD <Thai month name> YYYY' (B.E.) 
    and return a datetime.date in the Gregorian calendar.
    """
    try:
        parts = thai_date_str.split()
        if len(parts) != 3:
            raise ValueError(f"Invalid format: {thai_date_str!r}")
        
        day = int(parts[0])
        month_name = parts[1]
        year_be = int(parts[2])
        
        # Convert Buddhist year (B.E.) to Common Era (C.E.)
        year_ce = year_be - 543
        
        month = THAI_MONTHS.get(month_name)
        if not month:
            raise ValueError(f"Unknown Thai month name: {month_name!r}")
        
        return datetime(year_ce, month, day).date()
    except:
        return

# Example usage:


# Read DB settings from environment
DB_HOST     = "localhost"
DB_PORT     = 3306
DB_USER     = "admin"
DB_PASSWORD = "12345678"
DB_NAME     = "missing_persons_db"

API_URL = "https://api.thaimissing.go.th/api/v1/cir-Datacatalog-web/DataMissingPerson"

def fetch_data():
    with urllib.request.urlopen(API_URL, timeout=3000) as resp:
        return json.load(resp)

def handler():
    # 1) Fetch JSON
    records = fetch_data()
    print(records)

    # 2) Connect to RDS
    conn = pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, port=DB_PORT, cursorclass=pymysql.cursors.DictCursor
    )
    with conn:
        with conn.cursor() as cur:
            sql = """
            INSERT INTO missing_persons
              (full_name, age, gender, last_seen_location, last_seen_date,
               description, photo_url, source_url, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
              age=VALUES(age), gender=VALUES(gender),
              last_seen_location=VALUES(last_seen_location),
              last_seen_date=VALUES(last_seen_date),
              description=VALUES(description),
              photo_url=VALUES(photo_url),
              source_url=VALUES(source_url),
              status=VALUES(status);
            """
            for rec in records:
                # map JSON fields to your columns
                name = rec.get('fullName')
                try:
                    age  = int("".join(re.findall(r"\d", rec.get('ageInform'))))
                except:
                    age = None

                if(rec.get('sex') == "ชาย"):
                    gender = "male"
                else:
                    gender = "female"

                loc = rec.get('informLocation')
                raw = parse_thai_date(rec.get('missingDate'))
                try:
                    # seen_date = datetime.strptime(raw, '%Y-%m-%d').date()
                    seen_date = raw
                except:
                    seen_date = None
                desc = rec.get('cirNo')
                photo = rec.get('image')
                src = rec.get('url') or API_URL
                status = 'missing'

                cur.execute(sql, (
                    name, age, gender, loc, seen_date,
                    desc, photo, src, status
                ))
            conn.commit()

    return {
        'statusCode': 200,
        'body': json.dumps({'inserted': len(records)})
    }

handler()