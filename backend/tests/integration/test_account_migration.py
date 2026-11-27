"""A database from the single-user days is upgraded in place: nothing is lost and it all goes to the admin."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError

from src.core.storage.migrations import run_migrations

LEGACY_SQLITE = [
    """CREATE TABLE books (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, author TEXT DEFAULT 'Unknown',
        source_path TEXT NOT NULL, content_hash TEXT NOT NULL UNIQUE,
        total_chapters INTEGER NOT NULL DEFAULT 1, total_sentences INTEGER NOT NULL DEFAULT 0,
        total_words INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE bookmarks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, book_id INTEGER NOT NULL UNIQUE, current_chapter INTEGER NOT NULL DEFAULT 1,
        current_sentence_index INTEGER NOT NULL DEFAULT 0, completion_percentage REAL NOT NULL DEFAULT 0.0,
        last_read_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE reading_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, book_id INTEGER NOT NULL, start_time TIMESTAMP NOT NULL,
        end_time TIMESTAMP NOT NULL, duration_seconds INTEGER NOT NULL DEFAULT 0, sentences_read INTEGER NOT NULL DEFAULT 0,
        words_read INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE audio_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, book_id INTEGER NOT NULL, sentence_index INTEGER NOT NULL,
        start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL, note_text TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE voice_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT, voice_id TEXT NOT NULL UNIQUE, provider TEXT NOT NULL, display_name TEXT NOT NULL,
        language TEXT NOT NULL DEFAULT 'vi', gender TEXT, style TEXT, is_custom INTEGER NOT NULL DEFAULT 1,
        sample_path TEXT, consent_at TIMESTAMP, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
    "CREATE TABLE app_settings (setting_key TEXT PRIMARY KEY, setting_value TEXT NOT NULL)",
]


@pytest.fixture
def legacy_engine(tmp_path) -> Engine:
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        for ddl in LEGACY_SQLITE:
            conn.execute(text(ddl))
        for i, (title, pct, sentence) in enumerate((("Sách A", 100.0, 9), ("Sách B", 42.5, 4), ("Sách C", 0.0, 0)), 1):
            conn.execute(text("INSERT INTO books (title, source_path, content_hash, total_sentences) VALUES (:t, 'x', :h, 10)"),
                         {"t": title, "h": str(i) * 64})
            conn.execute(text("INSERT INTO bookmarks (book_id, current_sentence_index, completion_percentage) VALUES (:b, :s, :p)"),
                         {"b": i, "s": sentence, "p": pct})
        conn.execute(text("INSERT INTO reading_sessions (book_id, start_time, end_time, duration_seconds) VALUES (1, '2026-11-01 10:00:00', '2026-11-01 10:10:00', 600)"))
        conn.execute(text("INSERT INTO audio_notes (book_id, sentence_index, start_offset, end_offset, note_text) VALUES (1, 0, 0, 3, 'cũ')"))
        conn.execute(text("INSERT INTO voice_profiles (voice_id, provider, display_name) VALUES ('clone-old', 'heygen', 'Giọng cũ')"))
    return engine


def _scalar(engine: Engine, sql: str, **params):
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar()


def test_legacy_data_moves_to_the_admin_as_private_data(legacy_engine: Engine) -> None:
    run_migrations(legacy_engine)
    admin = _scalar(legacy_engine, "SELECT id FROM users WHERE role = 'admin'")
    assert admin is not None
    assert _scalar(legacy_engine, "SELECT COUNT(*) FROM books WHERE owner_id = :a AND is_public = 0", a=admin) == 3
    assert _scalar(legacy_engine, "SELECT owner_id FROM voice_profiles WHERE voice_id = 'clone-old'") == admin
    assert _scalar(legacy_engine, "SELECT user_id FROM audio_notes") == admin
    assert _scalar(legacy_engine, "SELECT user_id FROM reading_sessions") == admin
    assert _scalar(legacy_engine, "SELECT COUNT(*) FROM books") == 3  # nothing lost


def test_old_bookmarks_become_the_admins_progress(legacy_engine: Engine) -> None:
    run_migrations(legacy_engine)
    with legacy_engine.connect() as conn:
        rows = conn.execute(text("SELECT book_id, status, current_sentence_index, completion_percentage FROM user_book_progress ORDER BY book_id")).fetchall()
    assert [(r[0], r[1], r[2], r[3]) for r in rows] == [(1, "completed", 9, 100.0), (2, "reading", 4, 42.5), (3, "unread", 0, 0.0)]


def test_upgrading_twice_changes_nothing(legacy_engine: Engine) -> None:
    run_migrations(legacy_engine)
    with legacy_engine.begin() as conn:
        conn.execute(text("DELETE FROM user_book_progress WHERE book_id = 2"))  # the user later removed a book from their shelf
    run_migrations(legacy_engine)
    assert _scalar(legacy_engine, "SELECT COUNT(*) FROM users") == 1
    assert _scalar(legacy_engine, "SELECT COUNT(*) FROM user_book_progress") == 2  # not copied again
    assert _scalar(legacy_engine, "SELECT COUNT(*) FROM books") == 3


def test_book_uniqueness_becomes_per_owner(legacy_engine: Engine) -> None:
    run_migrations(legacy_engine)
    insert = "INSERT INTO books (title, source_path, content_hash, owner_id) VALUES ('Copy', 'x', :h, :o)"
    with legacy_engine.begin() as conn:
        conn.execute(text(insert), {"h": "1" * 64, "o": 77})  # same file as book 1, another owner: allowed now
    with pytest.raises(IntegrityError), legacy_engine.begin() as conn:
        conn.execute(text(insert), {"h": "1" * 64, "o": 77})  # same owner again: still refused


def test_the_rebuilt_books_table_keeps_its_ids(legacy_engine: Engine) -> None:
    run_migrations(legacy_engine)
    assert _scalar(legacy_engine, "SELECT title FROM books WHERE id = 2") == "Sách B"
    assert _scalar(legacy_engine, "SELECT MAX(id) FROM books") == 3
