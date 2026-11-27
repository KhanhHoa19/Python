-- Audiobook TTS: current MySQL 8 schema (tables only, no data).
--
-- Generated from a database brought up to date by the application's own migrations
-- (backend/src/core/storage/migrations.py), which remain the source of truth: they also upgrade older databases.
-- Regenerate after changing the schema:
--   docker exec studylab-mysql sh -c 'mysqldump -ustudylab -p"$MYSQL_PASSWORD" --no-data --skip-comments studylab_audiobook' > db/schema.sql
-- To start an empty database from this file: mysql studylab_audiobook < db/schema.sql

SET FOREIGN_KEY_CHECKS = 0;

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
CREATE TABLE IF NOT EXISTS `ambient_tracks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `file_name` varchar(64) NOT NULL,
  `size_bytes` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `app_settings` (
  `setting_key` varchar(128) NOT NULL,
  `setting_value` varchar(1024) NOT NULL,
  PRIMARY KEY (`setting_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `audio_notes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `book_id` int NOT NULL,
  `sentence_index` int NOT NULL,
  `start_offset` int NOT NULL,
  `end_offset` int NOT NULL,
  `note_text` text NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `user_id` int DEFAULT NULL,
  `emotion_tag` varchar(32) DEFAULT NULL,
  `context_before` text,
  `context_after` text,
  `audio_path` varchar(512) DEFAULT NULL,
  `voice` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_notes_book` (`book_id`),
  CONSTRAINT `audio_notes_ibfk_1` FOREIGN KEY (`book_id`) REFERENCES `books` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `book_sentences` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `book_id` int NOT NULL,
  `chapter_index` int NOT NULL DEFAULT '1',
  `sentence_index` int NOT NULL,
  `text_content` text NOT NULL,
  `word_count` int NOT NULL,
  `content_hash` char(64) NOT NULL,
  `cached_audio_path` varchar(1024) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_book_sentence` (`book_id`,`sentence_index`),
  KEY `idx_book_chapter` (`book_id`,`chapter_index`),
  CONSTRAINT `book_sentences_ibfk_1` FOREIGN KEY (`book_id`) REFERENCES `books` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `bookmarks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `book_id` int NOT NULL,
  `current_chapter` int NOT NULL DEFAULT '1',
  `current_sentence_index` int NOT NULL DEFAULT '0',
  `completion_percentage` float NOT NULL DEFAULT '0',
  `last_read_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `voice` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `book_id` (`book_id`),
  CONSTRAINT `bookmarks_ibfk_1` FOREIGN KEY (`book_id`) REFERENCES `books` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `books` (
  `id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(255) NOT NULL,
  `author` varchar(255) DEFAULT 'Unknown',
  `source_path` varchar(1024) NOT NULL,
  `content_hash` char(64) NOT NULL,
  `total_chapters` int NOT NULL DEFAULT '1',
  `total_sentences` int NOT NULL DEFAULT '0',
  `total_words` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `owner_id` int DEFAULT NULL,
  `is_public` smallint NOT NULL DEFAULT '0',
  `category_id` int DEFAULT NULL,
  `cover_path` varchar(64) DEFAULT NULL,
  `search_text` varchar(600) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_books_owner_hash` (`owner_id`,`content_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `categories` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(64) NOT NULL,
  `slug` varchar(64) NOT NULL,
  `icon` varchar(32) NOT NULL DEFAULT 'book',
  `color` varchar(16) NOT NULL DEFAULT '#8a6d3b',
  `sort_order` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  UNIQUE KEY `slug` (`slug`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `document_chapters` (
  `id` int NOT NULL AUTO_INCREMENT,
  `book_id` int NOT NULL,
  `chapter_index` int NOT NULL,
  `title` varchar(255) NOT NULL,
  `start_sentence_index` int NOT NULL,
  `end_sentence_index` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_book_chapter` (`book_id`,`chapter_index`),
  CONSTRAINT `document_chapters_ibfk_1` FOREIGN KEY (`book_id`) REFERENCES `books` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `network_metrics` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `session_id` int NOT NULL,
  `sentence_index` int NOT NULL,
  `response_time_seconds` float NOT NULL,
  `lan_ping_ms` float DEFAULT NULL,
  `tailscale_ping_ms` float DEFAULT NULL,
  `status` varchar(32) NOT NULL DEFAULT 'SUCCESS',
  `recorded_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_session_sentence` (`session_id`,`sentence_index`),
  KEY `idx_recorded_at` (`recorded_at`),
  CONSTRAINT `network_metrics_ibfk_1` FOREIGN KEY (`session_id`) REFERENCES `reading_sessions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `reading_sessions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `book_id` int NOT NULL,
  `start_time` datetime NOT NULL,
  `end_time` datetime NOT NULL,
  `duration_seconds` int NOT NULL DEFAULT '0',
  `sentences_read` int NOT NULL DEFAULT '0',
  `words_read` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `voice` varchar(255) DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `book_id` (`book_id`),
  CONSTRAINT `reading_sessions_ibfk_1` FOREIGN KEY (`book_id`) REFERENCES `books` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `user_book_progress` (
  `user_id` int NOT NULL,
  `book_id` int NOT NULL,
  `status` varchar(16) NOT NULL DEFAULT 'unread',
  `is_favorite` tinyint(1) NOT NULL DEFAULT '0',
  `current_chapter` int NOT NULL DEFAULT '1',
  `current_sentence_index` int NOT NULL DEFAULT '0',
  `completion_percentage` float NOT NULL DEFAULT '0',
  `voice` varchar(255) DEFAULT NULL,
  `speed` float DEFAULT NULL,
  `last_read_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`,`book_id`),
  KEY `book_id` (`book_id`),
  CONSTRAINT `user_book_progress_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `user_book_progress_ibfk_2` FOREIGN KEY (`book_id`) REFERENCES `books` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `user_settings` (
  `user_id` int NOT NULL,
  `setting_key` varchar(128) NOT NULL,
  `setting_value` varchar(1024) NOT NULL,
  PRIMARY KEY (`user_id`,`setting_key`),
  CONSTRAINT `user_settings_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(64) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `full_name` varchar(255) NOT NULL,
  `role` varchar(16) NOT NULL DEFAULT 'user',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `voice_profiles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `voice_id` varchar(255) NOT NULL,
  `provider` varchar(64) NOT NULL,
  `display_name` varchar(255) NOT NULL,
  `language` varchar(16) NOT NULL DEFAULT 'vi',
  `gender` varchar(16) DEFAULT NULL,
  `style` varchar(64) DEFAULT NULL,
  `is_custom` tinyint(1) NOT NULL DEFAULT '1',
  `sample_path` varchar(1024) DEFAULT NULL,
  `consent_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `owner_id` int DEFAULT NULL,
  `is_public` smallint NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `voice_id` (`voice_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

SET FOREIGN_KEY_CHECKS = 1;
