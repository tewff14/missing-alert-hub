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
# def get_db_credentials():
#     """If using Secrets Manager, fetch credentials; otherwise rely on ENV vars."""
#     secret_arn = os.environ.get('SECRET_ARN')
#     if secret_arn:
#         client = boto3.client('secretsmanager')
#         resp = client.get_secret_value(SecretId=secret_arn)
#         data = json.loads(resp['SecretString'])
#         return (data['host'], int(data.get('port',3306)),
#                 data['username'], data['password'], data['dbname'])
#     else:
#         return (
#             os.environ['DB_HOST'],
#             int(os.environ.get('DB_PORT', 3306)),
#             os.environ['DB_USER'],
#             os.environ['DB_PASSWORD'],
#             os.environ['DB_NAME']
#         )

def lambda_handler():
    # --- 1) Load config ---
    api_url = "https://api.thaimissing.go.th/api/v1/cir-Datacatalog-web/DataMissingPerson"
    # host, port, user, pwd, db = get_db_credentials()
    # Read DB settings from environment
    host     = "localhost"
    port     = 3306
    user     = "admin"
    pwd = "12345678"
    db     = "missing_persons_db"

    # --- 2) Connect to RDS ---
    conn = pymysql.connect(
        host=host, port=port, user=user,
        password=pwd, database=db,
        cursorclass=pymysql.cursors.DictCursor
    )

    # --- 3) Prepare upsert SQL ---
    upsert_sql = """
    INSERT INTO missing_persons (
      id, cir_no, full_name, nationality,
      age_missing, age_current, age_inform,
      gender, missing_date, missing_time,
      missing_location, inform_location,
      photo_url, source_url
    ) VALUES (
      %(id)s, %(cir_no)s, %(full_name)s, %(nationality)s,
      %(age_missing)s, %(age_current)s, %(age_inform)s,
      %(gender)s, %(missing_date)s, %(missing_time)s,
      %(missing_location)s, %(inform_location)s,
      %(photo_url)s, %(source_url)s
    )
    ON DUPLICATE KEY UPDATE
      cir_no=VALUES(cir_no),
      full_name=VALUES(full_name),
      nationality=VALUES(nationality),
      age_missing=VALUES(age_missing),
      age_current=VALUES(age_current),
      age_inform=VALUES(age_inform),
      gender=VALUES(gender),
      missing_date=VALUES(missing_date),
      missing_time=VALUES(missing_time),
      missing_location=VALUES(missing_location),
      inform_location=VALUES(inform_location),
      photo_url=VALUES(photo_url),
      source_url=VALUES(source_url);
    """

    # --- 4) Fetch API data ---
    resp = urllib.request.urlopen(api_url)
    data = json.loads(resp.read().decode('utf-8'))


    # --- 5) Insert/Upsert each record ---
    count = 0
    with conn.cursor() as cur:
        for rec in data:
            
            #sensitive variable
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
            


            payload = {
                'id':           int(rec.get('id')),
                'cir_no':       rec.get('cirNo'),
                'full_name':    rec.get('fullName'),
                'nationality':  rec.get('nationality'),
                'age_missing':  age_missing,
                'age_current':  age_current,
                'age_inform':   age_inform,
                'gender':       rec.get('sex'),
                'missing_date': parse_thai_date(rec.get('missingDate')),
                'missing_time': parse_thai_time(rec.get('missingTime')),
                'missing_location': rec.get('missingLocation'),
                'inform_location':  rec.get('informLocation'),
                'photo_url':    rec.get('image'),
                'source_url':   rec.get('url')
            }
            cur.execute(upsert_sql, payload)
            count += 1
        conn.commit()

    return {
        'statusCode': 200,
        'body': json.dumps({'processed': count})
    }

lambda_handler()