CREATE TABLE `cases` (
  `id` integer PRIMARY KEY AUTO_INCREMENT,
  `name` varchar(255),
  `created_at` timestamp
);

CREATE TABLE `case_information` (
  `case_id` integer,
  `platform` varchar(255),
  `picture` varchar(255),
  `url` varchar(255),
  `description` varchar(5000),
  `created_at` timestamp,
  PRIMARY KEY (`case_id`, `platform`)
);

CREATE TABLE `posted_case` (
  `case_id` integer,
  `social_platform` varchar(255),
  `posted_at` timestamp,
  `url` varchar(255),
  PRIMARY KEY (`case_id`, `social_platform`)
);

ALTER TABLE `case_information` ADD CONSTRAINT `case_information` FOREIGN KEY (`case_id`) REFERENCES `cases` (`id`);

ALTER TABLE `posted_case` ADD CONSTRAINT `post` FOREIGN KEY (`case_id`) REFERENCES `cases` (`id`);