-- 1. Create the database
CREATE DATABASE IF NOT EXISTS missing_persons_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE missing_persons_db;

-- 2. Create the table
CREATE TABLE IF NOT EXISTS missing_persons (
  id               INT              NOT NULL COMMENT 'API record ID',
  cir_no           VARCHAR(50)      NOT NULL COMMENT 'CIR number',
  full_name        VARCHAR(255)     NOT NULL COMMENT 'ชื่อ-สกุล',
  nationality      VARCHAR(100)     DEFAULT NULL COMMENT 'สัญชาติ',
  age_missing      INT              DEFAULT NULL COMMENT 'อายุขณะหายตัว',
  age_current      INT              DEFAULT NULL COMMENT 'อายุปัจจุบัน',
  age_inform       INT              DEFAULT NULL COMMENT 'อายุที่ได้รับแจ้ง',
  gender           ENUM('ชาย','หญิง','อื่นๆ') DEFAULT NULL COMMENT 'เพศ',
  missing_date     DATE             DEFAULT NULL COMMENT 'วันที่หายตัว',
  missing_time     TIME             DEFAULT NULL COMMENT 'เวลาที่หายตัว',
  missing_location VARCHAR(255)     DEFAULT NULL COMMENT 'สถานที่หายตัว',
  inform_location  VARCHAR(255)     DEFAULT NULL COMMENT 'สถานที่แจ้งเหตุ',
  photo_url        VARCHAR(500)     DEFAULT NULL COMMENT 'URL รูปพยานหลักฐาน',
  source_url       VARCHAR(500)     DEFAULT NULL COMMENT 'URL หน้า missing person',
  created_at       TIMESTAMP        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'เวลาบันทึก',
  PRIMARY KEY (id),
  KEY idx_missing_date (missing_date),
  KEY idx_cir_no       (cir_no)
) ENGINE=InnoDB;