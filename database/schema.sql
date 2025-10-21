CREATE TABLE IF NOT EXISTS `hunters` (
  `steam_id` varchar(20) NOT NULL PRIMARY KEY,
  `steam_name` varchar(100) NOT NULL DEFAULT 'Unknown',
  `discord_id` varchar(20) DEFAULT NULL,
  `score` int(11) NOT NULL DEFAULT '0',
  `total_achievements` int(11) NOT NULL DEFAULT '0',
  `total_games` int(11) NOT NULL DEFAULT '0',
  `last_updated` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `locked` boolean NOT NULL DEFAULT 0
);

-- API Statistics tracking
CREATE TABLE IF NOT EXISTS `api_statistics` (
  `id` INTEGER PRIMARY KEY AUTOINCREMENT,
  `date` DATE NOT NULL UNIQUE,
  `total_calls` INTEGER NOT NULL DEFAULT 0,
  `resolve_vanity_url` INTEGER NOT NULL DEFAULT 0,
  `get_player_summaries` INTEGER NOT NULL DEFAULT 0,
  `get_owned_games` INTEGER NOT NULL DEFAULT 0,
  `get_player_achievements` INTEGER NOT NULL DEFAULT 0,
  `get_schema_for_game` INTEGER NOT NULL DEFAULT 0,
  `get_user_stats_for_game` INTEGER NOT NULL DEFAULT 0,
  `get_recently_played_games` INTEGER NOT NULL DEFAULT 0,
  `get_global_achievement_percentages` INTEGER NOT NULL DEFAULT 0,
  `failed_calls` INTEGER NOT NULL DEFAULT 0,
  `rate_limit_hits` INTEGER NOT NULL DEFAULT 0,
  `private_profile_errors` INTEGER NOT NULL DEFAULT 0,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- API Call Log (detailed tracking with timestamps)
CREATE TABLE IF NOT EXISTS `api_call_log` (
  `id` INTEGER PRIMARY KEY AUTOINCREMENT,
  `timestamp` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `endpoint` varchar(100) NOT NULL,
  `steam_id` varchar(20) DEFAULT NULL,
  `app_id` INTEGER DEFAULT NULL,
  `success` boolean NOT NULL DEFAULT 1,
  `error_type` varchar(50) DEFAULT NULL,
  `response_time_ms` INTEGER DEFAULT NULL
);

-- Index for faster queries
CREATE INDEX IF NOT EXISTS `idx_api_statistics_date` ON `api_statistics` (`date`);
CREATE INDEX IF NOT EXISTS `idx_api_call_log_timestamp` ON `api_call_log` (`timestamp`);
CREATE INDEX IF NOT EXISTS `idx_api_call_log_endpoint` ON `api_call_log` (`endpoint`);