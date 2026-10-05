CREATE TABLE `audit_events` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`previous` text NOT NULL,
	`hash` text NOT NULL,
	`payload` text NOT NULL,
	`signature` text NOT NULL,
	`key_id` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_audit_previous` ON `audit_events` (`previous`);--> statement-breakpoint
CREATE TABLE `entities` (
	`id` text PRIMARY KEY NOT NULL,
	`kind` text NOT NULL,
	`data` text NOT NULL,
	`created` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_entities_kind_created` ON `entities` (`kind`,`created`);--> statement-breakpoint
CREATE TABLE `graph_edges` (
	`source` text NOT NULL,
	`target` text NOT NULL,
	`relation` text NOT NULL,
	PRIMARY KEY(`source`, `target`, `relation`)
);
--> statement-breakpoint
CREATE INDEX `idx_graph_edges_target` ON `graph_edges` (`target`);--> statement-breakpoint
CREATE TABLE `key_store` (
	`id` text PRIMARY KEY NOT NULL,
	`public_key` text NOT NULL,
	`encrypted` text NOT NULL,
	`certificate` text NOT NULL,
	`status` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `replay_nonces` (
	`nonce` text PRIMARY KEY NOT NULL,
	`sensor` text NOT NULL,
	`sequence` integer NOT NULL,
	`record_id` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_replay_sensor_sequence` ON `replay_nonces` (`sensor`,`sequence`);