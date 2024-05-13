-- Your SQL goes here
CREATE TABLE `transactions`(
	`id` TEXT NOT NULL PRIMARY KEY,
	`ticker` TEXT NOT NULL,
	`num_sold` INTEGER NOT NULL,
	`price` FLOAT NOT NULL,
	`date` INTEGER NOT NULL,
	`description` TEXT
);

