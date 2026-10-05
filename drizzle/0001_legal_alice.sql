CREATE TABLE `stream_heads` (
	`sensor` text PRIMARY KEY NOT NULL,
	`sequence` integer NOT NULL,
	`hash` text NOT NULL
);
