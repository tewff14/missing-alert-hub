CREATE TABLE "cases" (
  "id" integer PRIMARY KEY,
  "missing_person_name" varchar,
  "gender" varchar,
  "created_at" timestamp
);

CREATE TABLE "case_information" (
  "case_id" integer,
  "platform" varchar,
  "picture" path,
  "description" varchar,
  "created_at" timestamp,
  PRIMARY KEY ("case_id", "platform")
);

CREATE TABLE "posted_case" (
  "case_id" integer,
  "posted_at" timestamp,
  "platform" varchar,
  "url" varchar,
  PRIMARY KEY ("case_id", "posted_at")
);

ALTER TABLE "case_information" ADD CONSTRAINT "case_information" FOREIGN KEY ("case_id") REFERENCES "cases" ("id");

ALTER TABLE "posted_case" ADD CONSTRAINT "post" FOREIGN KEY ("case_id") REFERENCES "cases" ("id");
