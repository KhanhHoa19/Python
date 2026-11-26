"""Database schema migration runner (books, sentences, bookmarks, sessions, metrics, voices, notes, settings)."""

from __future__ import annotations

import logging

from sqlalchemy import Engine, text

from src.core.storage.db import get_db_engine

logger = logging.getLogger(__name__)

MYSQL_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS books (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        author VARCHAR(255) DEFAULT 'Unknown',
        source_path VARCHAR(1024) NOT NULL,
        content_hash CHAR(64) NOT NULL UNIQUE,
        total_chapters INT NOT NULL DEFAULT 1,
        total_sentences INT NOT NULL DEFAULT 0,
        total_words INT NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS book_sentences (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        book_id INT NOT NULL,
        chapter_index INT NOT NULL DEFAULT 1,
        sentence_index INT NOT NULL,
        text_content TEXT NOT NULL,
        word_count INT NOT NULL,
        content_hash CHAR(64) NOT NULL,
        cached_audio_path VARCHAR(1024) DEFAULT NULL,
        UNIQUE KEY uk_book_sentence (book_id, sentence_index),
        INDEX idx_book_chapter (book_id, chapter_index),
        FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS bookmarks (
        id INT AUTO_INCREMENT PRIMARY KEY,
        book_id INT NOT NULL UNIQUE,
        current_chapter INT NOT NULL DEFAULT 1,
        current_sentence_index INT NOT NULL DEFAULT 0,
        completion_percentage FLOAT NOT NULL DEFAULT 0.0,
        last_read_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS reading_sessions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        book_id INT NOT NULL,
        start_time DATETIME NOT NULL,
        end_time DATETIME NOT NULL,
        duration_seconds INT NOT NULL DEFAULT 0,
        sentences_read INT NOT NULL DEFAULT 0,
        words_read INT NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS network_metrics (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        session_id INT NOT NULL,
        sentence_index INT NOT NULL,
        response_time_seconds FLOAT NOT NULL,
        lan_ping_ms FLOAT DEFAULT NULL,
        tailscale_ping_ms FLOAT DEFAULT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'SUCCESS',
        recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_session_sentence (session_id, sentence_index),
        INDEX idx_recorded_at (recorded_at),
        FOREIGN KEY (session_id) REFERENCES reading_sessions (id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS voice_profiles (
        id INT AUTO_INCREMENT PRIMARY KEY,
        voice_id VARCHAR(255) NOT NULL UNIQUE,
        provider VARCHAR(64) NOT NULL,
        display_name VARCHAR(255) NOT NULL,
        language VARCHAR(16) NOT NULL DEFAULT 'vi',
        gender VARCHAR(16) DEFAULT NULL,
        style VARCHAR(64) DEFAULT NULL,
        is_custom TINYINT(1) NOT NULL DEFAULT 1,
        sample_path VARCHAR(1024) DEFAULT NULL,
        consent_at DATETIME DEFAULT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS audio_notes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        book_id INT NOT NULL,
        sentence_index INT NOT NULL,
        start_offset INT NOT NULL,
        end_offset INT NOT NULL,
        note_text TEXT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_notes_book (book_id),
        FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS app_settings (
        setting_key VARCHAR(128) PRIMARY KEY,
        setting_value VARCHAR(1024) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
]

SQLITE_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT DEFAULT 'Unknown',
        source_path TEXT NOT NULL,
        content_hash TEXT NOT NULL UNIQUE,
        total_chapters INTEGER NOT NULL DEFAULT 1,
        total_sentences INTEGER NOT NULL DEFAULT 0,
        total_words INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS book_sentences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL,
        chapter_index INTEGER NOT NULL DEFAULT 1,
        sentence_index INTEGER NOT NULL,
        text_content TEXT NOT NULL,
        word_count INTEGER NOT NULL,
        content_hash TEXT NOT NULL,
        cached_audio_path TEXT DEFAULT NULL,
        UNIQUE (book_id, sentence_index),
        FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS bookmarks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL UNIQUE,
        current_chapter INTEGER NOT NULL DEFAULT 1,
        current_sentence_index INTEGER NOT NULL DEFAULT 0,
        completion_percentage REAL NOT NULL DEFAULT 0.0,
        last_read_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS reading_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL,
        start_time TIMESTAMP NOT NULL,
        end_time TIMESTAMP NOT NULL,
        duration_seconds INTEGER NOT NULL DEFAULT 0,
        sentences_read INTEGER NOT NULL DEFAULT 0,
        words_read INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS network_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        sentence_index INTEGER NOT NULL,
        response_time_seconds REAL NOT NULL,
        lan_ping_ms REAL DEFAULT NULL,
        tailscale_ping_ms REAL DEFAULT NULL,
        status TEXT NOT NULL DEFAULT 'SUCCESS',
        recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES reading_sessions (id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS voice_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        voice_id TEXT NOT NULL UNIQUE,
        provider TEXT NOT NULL,
        display_name TEXT NOT NULL,
        language TEXT NOT NULL DEFAULT 'vi',
        gender TEXT DEFAULT NULL,
        style TEXT DEFAULT NULL,
        is_custom INTEGER NOT NULL DEFAULT 1,
        sample_path TEXT DEFAULT NULL,
        consent_at TIMESTAMP DEFAULT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS audio_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL,
        sentence_index INTEGER NOT NULL,
        start_offset INTEGER NOT NULL,
        end_offset INTEGER NOT NULL,
        note_text TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS app_settings (
        setting_key TEXT PRIMARY KEY,
        setting_value TEXT NOT NULL
    );
    """,
]


def run_migrations(engine: Engine | None = None) -> None:
    """Execute table creation DDL statements on the configured database."""
    eng = engine or get_db_engine()
    is_sqlite = eng.url.drivername.startswith("sqlite")
    statements = SQLITE_TABLES if is_sqlite else MYSQL_TABLES

    logger.info(f"Running database schema migrations (driver={eng.url.drivername})...")
    with eng.connect() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
        conn.commit()
    logger.info("Database schema migrations completed successfully.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_migrations()
