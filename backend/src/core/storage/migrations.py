"""Database schema migration runner (books, sentences, chapters, bookmarks, sessions, metrics, voices, notes, settings)."""

from __future__ import annotations

import logging

from sqlalchemy import Engine, inspect, text

from src.core.storage.db import get_db_engine

logger = logging.getLogger(__name__)

MYSQL_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS books (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        author VARCHAR(255) DEFAULT 'Unknown',
        source_path VARCHAR(1024) NOT NULL,
        content_hash CHAR(64) NOT NULL,
        total_chapters INT NOT NULL DEFAULT 1,
        total_sentences INT NOT NULL DEFAULT 0,
        total_words INT NOT NULL DEFAULT 0,
        owner_id INT DEFAULT NULL,
        is_public TINYINT(1) NOT NULL DEFAULT 0,
        category_id INT DEFAULT NULL,
        cover_path VARCHAR(64) DEFAULT NULL,
        search_text VARCHAR(600) DEFAULT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_books_owner_hash (owner_id, content_hash)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS categories (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(64) NOT NULL UNIQUE,
        slug VARCHAR(64) NOT NULL UNIQUE,
        icon VARCHAR(32) NOT NULL DEFAULT 'book',
        color VARCHAR(16) NOT NULL DEFAULT '#8a6d3b',
        sort_order INT NOT NULL DEFAULT 0
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(64) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        full_name VARCHAR(255) NOT NULL,
        role VARCHAR(16) NOT NULL DEFAULT 'user',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS user_book_progress (
        user_id INT NOT NULL,
        book_id INT NOT NULL,
        status VARCHAR(16) NOT NULL DEFAULT 'unread',
        is_favorite TINYINT(1) NOT NULL DEFAULT 0,
        current_chapter INT NOT NULL DEFAULT 1,
        current_sentence_index INT NOT NULL DEFAULT 0,
        completion_percentage FLOAT NOT NULL DEFAULT 0.0,
        voice VARCHAR(255) DEFAULT NULL,
        speed FLOAT DEFAULT NULL,
        last_read_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, book_id),
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS user_settings (
        user_id INT NOT NULL,
        setting_key VARCHAR(128) NOT NULL,
        setting_value VARCHAR(1024) NOT NULL,
        PRIMARY KEY (user_id, setting_key),
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
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
    CREATE TABLE IF NOT EXISTS document_chapters (
        id INT AUTO_INCREMENT PRIMARY KEY,
        book_id INT NOT NULL,
        chapter_index INT NOT NULL,
        title VARCHAR(255) NOT NULL,
        start_sentence_index INT NOT NULL,
        end_sentence_index INT NOT NULL,
        UNIQUE KEY uk_book_chapter (book_id, chapter_index),
        FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS app_settings (
        setting_key VARCHAR(128) PRIMARY KEY,
        setting_value VARCHAR(1024) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS ambient_tracks (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        file_name VARCHAR(64) NOT NULL,
        size_bytes INT NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
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
        content_hash TEXT NOT NULL,
        total_chapters INTEGER NOT NULL DEFAULT 1,
        total_sentences INTEGER NOT NULL DEFAULT 0,
        total_words INTEGER NOT NULL DEFAULT 0,
        owner_id INTEGER DEFAULT NULL,
        is_public INTEGER NOT NULL DEFAULT 0,
        category_id INTEGER DEFAULT NULL,
        cover_path TEXT DEFAULT NULL,
        search_text TEXT DEFAULT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (owner_id, content_hash)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        slug TEXT NOT NULL UNIQUE,
        icon TEXT NOT NULL DEFAULT 'book',
        color TEXT NOT NULL DEFAULT '#8a6d3b',
        sort_order INTEGER NOT NULL DEFAULT 0
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS user_book_progress (
        user_id INTEGER NOT NULL,
        book_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'unread',
        is_favorite INTEGER NOT NULL DEFAULT 0,
        current_chapter INTEGER NOT NULL DEFAULT 1,
        current_sentence_index INTEGER NOT NULL DEFAULT 0,
        completion_percentage REAL NOT NULL DEFAULT 0.0,
        voice TEXT DEFAULT NULL,
        speed REAL DEFAULT NULL,
        last_read_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, book_id),
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS user_settings (
        user_id INTEGER NOT NULL,
        setting_key TEXT NOT NULL,
        setting_value TEXT NOT NULL,
        PRIMARY KEY (user_id, setting_key),
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
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
    CREATE TABLE IF NOT EXISTS document_chapters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL,
        chapter_index INTEGER NOT NULL,
        title TEXT NOT NULL,
        start_sentence_index INTEGER NOT NULL,
        end_sentence_index INTEGER NOT NULL,
        UNIQUE (book_id, chapter_index),
        FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS app_settings (
        setting_key TEXT PRIMARY KEY,
        setting_value TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS ambient_tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        file_name TEXT NOT NULL,
        size_bytes INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
]


# Columns added after the first release. CREATE TABLE IF NOT EXISTS never alters an existing table,
# so databases created earlier get these through ALTER TABLE ... ADD COLUMN (table, column, definition).
COLUMN_UPGRADES: list[tuple[str, str, str]] = [
    ("reading_sessions", "voice", "VARCHAR(255) DEFAULT NULL"),
    ("bookmarks", "voice", "VARCHAR(255) DEFAULT NULL"),
    # accounts: data created before them is moved to the admin by `bootstrap_accounts`
    ("books", "owner_id", "INT DEFAULT NULL"),
    ("books", "is_public", "SMALLINT NOT NULL DEFAULT 0"),
    ("books", "category_id", "INT DEFAULT NULL"),
    ("books", "cover_path", "VARCHAR(64) DEFAULT NULL"),
    ("books", "search_text", "VARCHAR(600) DEFAULT NULL"),
    ("voice_profiles", "owner_id", "INT DEFAULT NULL"),
    ("voice_profiles", "is_public", "SMALLINT NOT NULL DEFAULT 0"),
    ("audio_notes", "user_id", "INT DEFAULT NULL"),
    ("reading_sessions", "user_id", "INT DEFAULT NULL"),
    # quotes: audio_notes grew into "Trích dẫn yêu thích" (one-tap bookmarks with a feeling, context and a saved audio file)
    ("audio_notes", "emotion_tag", "VARCHAR(32) DEFAULT NULL"),
    ("audio_notes", "context_before", "TEXT DEFAULT NULL"),
    ("audio_notes", "context_after", "TEXT DEFAULT NULL"),
    ("audio_notes", "audio_path", "VARCHAR(512) DEFAULT NULL"),
    ("audio_notes", "voice", "VARCHAR(255) DEFAULT NULL"),
]


def upgrade_columns(engine: Engine) -> list[str]:
    """Add every missing column of COLUMN_UPGRADES. Returns the "table.column" names it added."""
    existing: dict[str, set[str]] = {}
    added: list[str] = []
    with engine.begin() as conn:
        inspector = inspect(conn)
        for table, column, definition in COLUMN_UPGRADES:
            if not inspector.has_table(table):
                continue
            if table not in existing:
                existing[table] = {c["name"] for c in inspector.get_columns(table)}
            if column not in existing[table]:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
                existing[table].add(column)
                added.append(f"{table}.{column}")
    return added


def replace_books_unique(engine: Engine) -> bool:
    """A book is unique per owner, not globally: UNIQUE(content_hash) becomes UNIQUE(owner_id, content_hash),
    so two people can each own the same file. Needed only for databases created before accounts.
    Returns True if something was changed."""
    inspector = inspect(engine)
    legacy: list[dict] = [
        dict(u) for u in inspector.get_unique_constraints("books") if list(u["column_names"]) == ["content_hash"]
    ]
    legacy += [dict(i) for i in inspector.get_indexes("books") if i.get("unique") and list(i["column_names"]) == ["content_hash"]]
    if not legacy:
        return False
    if engine.url.drivername.startswith("sqlite"):
        _rebuild_sqlite_books(engine)
        return True
    with engine.begin() as conn:
        for name in {u["name"] for u in legacy if u.get("name")}:
            conn.execute(text(f"ALTER TABLE books DROP INDEX `{name}`"))  # noqa: S608
        conn.execute(text("ALTER TABLE books ADD UNIQUE KEY uk_books_owner_hash (owner_id, content_hash)"))
    return True


def _rebuild_sqlite_books(engine: Engine) -> None:
    """SQLite cannot drop a UNIQUE constraint: copy the rows into a table with the new definition."""
    create_new = SQLITE_TABLES[0].replace("CREATE TABLE IF NOT EXISTS books (", "CREATE TABLE books_new (", 1)
    columns = "id, title, author, source_path, content_hash, total_chapters, total_sentences, total_words, owner_id, is_public, category_id, cover_path, search_text, created_at, updated_at"
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.commit()  # the pragma only works outside a transaction
        with conn.begin():
            conn.execute(text(create_new))
            conn.execute(text(f"INSERT INTO books_new ({columns}) SELECT {columns} FROM books"))  # noqa: S608
            conn.execute(text("DROP TABLE books"))
            conn.execute(text("ALTER TABLE books_new RENAME TO books"))


def bootstrap_accounts(engine: Engine) -> None:
    """Make sure an admin exists and that data from the single-user days belongs to that admin."""
    from src.core.auth.users import assign_legacy_data, ensure_admin

    assign_legacy_data(engine, ensure_admin(engine))
    from src.core.config import get_settings
    from src.core.storage.library import backfill_book_extras, ensure_default_categories

    ensure_default_categories(engine)
    backfill_book_extras(engine)
    if get_settings().dev_quick_login:
        from src.core.auth.demo_accounts import seed_demo_accounts

        seed_demo_accounts(engine)


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
    for name in upgrade_columns(eng):
        logger.info("Added missing column %s", name)
    if replace_books_unique(eng):
        logger.info("books: UNIQUE(content_hash) replaced by UNIQUE(owner_id, content_hash)")
    bootstrap_accounts(eng)
    logger.info("Database schema migrations completed successfully.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_migrations()
