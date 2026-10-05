CREATE TABLE `app_login_attempts` (
	`id` text PRIMARY KEY NOT NULL,
	`failures` integer NOT NULL,
	`locked_until` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `app_sessions` (
	`token_hash` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`expires_at` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_app_sessions_expiry` ON `app_sessions` (`expires_at`);--> statement-breakpoint
CREATE TABLE `app_users` (
	`id` text PRIMARY KEY NOT NULL,
	`username` text NOT NULL,
	`account_role` text NOT NULL,
	`role` text NOT NULL,
	`password_hash` text NOT NULL,
	`salt` text NOT NULL,
	`contributor_id` text,
	`active` integer DEFAULT 1 NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `idx_app_users_username` ON `app_users` (`username`);