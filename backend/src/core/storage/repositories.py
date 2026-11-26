"""Parameterized SQL repository implementations for books, bookmarks, sessions, and telemetry."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Engine, text

from src.core.models.book import Book, Bookmark, BookSentence
from src.core.models.session import ReadingSession
from src.core.models.telemetry import NetworkMetric

logger = logging.getLogger(__name__)


class SqlBookRepository:
    """Manages persistence and retrieval for books and sentences."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def save_book(self, book: Book, sentences: list[BookSentence]) -> int:
        """Insert book and sentences atomically within a transaction. Returns book_id."""
        with self.engine.begin() as conn:
            # 1. Insert book
            insert_book_sql = text("""
                INSERT INTO books (title, author, source_path, content_hash, total_chapters, total_sentences, total_words)
                VALUES (:title, :author, :source_path, :content_hash, :total_chapters, :total_sentences, :total_words)
            """)
            result = conn.execute(insert_book_sql, {
                "title": book.title,
                "author": book.author,
                "source_path": book.source_path,
                "content_hash": book.content_hash,
                "total_chapters": book.total_chapters,
                "total_sentences": book.total_sentences,
                "total_words": book.total_words,
            })
            book_id = result.lastrowid
            if book_id is None:
                # SQLite fallback rowid fetch
                book_id = conn.execute(text("SELECT last_insert_rowid()")).scalar()

            # 2. Batch insert sentences
            if sentences:
                insert_sentence_sql = text("""
                    INSERT INTO book_sentences (book_id, chapter_index, sentence_index, text_content, word_count, content_hash, cached_audio_path)
                    VALUES (:book_id, :chapter_index, :sentence_index, :text_content, :word_count, :content_hash, :cached_audio_path)
                """)
                params = [
                    {
                        "book_id": book_id,
                        "chapter_index": s.chapter_index,
                        "sentence_index": s.sentence_index,
                        "text_content": s.text_content,
                        "word_count": s.word_count,
                        "content_hash": s.content_hash,
                        "cached_audio_path": s.cached_audio_path,
                    }
                    for s in sentences
                ]
                conn.execute(insert_sentence_sql, params)

            # 3. Create initial bookmark at sentence index 0
            insert_bookmark_sql = text("""
                INSERT INTO bookmarks (book_id, current_chapter, current_sentence_index, completion_percentage)
                VALUES (:book_id, 1, 0, 0.0)
            """)
            conn.execute(insert_bookmark_sql, {"book_id": book_id})

            book.id = book_id
            return book_id

    def get_by_id(self, book_id: int) -> Book | None:
        """Fetch book by surrogate ID."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, title, author, source_path, content_hash, total_chapters, total_sentences, total_words, created_at, updated_at FROM books WHERE id = :id"),
                {"id": book_id}
            ).fetchone()
            if not row:
                return None
            return Book(
                id=row[0],
                title=row[1],
                author=row[2],
                source_path=row[3],
                content_hash=row[4],
                total_chapters=row[5],
                total_sentences=row[6],
                total_words=row[7],
                created_at=row[8],
                updated_at=row[9],
            )

    def get_book(self, book_id: int) -> Book | None:
        """Alias for get_by_id."""
        return self.get_by_id(book_id)

    def get_book_sentences(self, book_id: int) -> list[BookSentence]:
        """Fetch all sentences for a book."""
        return self.get_sentences(book_id, start_idx=0, limit=100000)

    def get_by_hash(self, content_hash: str) -> Book | None:
        """Fetch book by SHA-256 content hash."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, title, author, source_path, content_hash, total_chapters, total_sentences, total_words, created_at, updated_at FROM books WHERE content_hash = :hash"),
                {"hash": content_hash}
            ).fetchone()
            if not row:
                return None
            return Book(
                id=row[0],
                title=row[1],
                author=row[2],
                source_path=row[3],
                content_hash=row[4],
                total_chapters=row[5],
                total_sentences=row[6],
                total_words=row[7],
                created_at=row[8],
                updated_at=row[9],
            )

    def list_books(self, limit: int = 50, offset: int = 0) -> list[Book]:
        """List cataloged books ordered by created_at desc."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id, title, author, source_path, content_hash, total_chapters, total_sentences, total_words, created_at, updated_at FROM books ORDER BY id DESC LIMIT :limit OFFSET :offset"),
                {"limit": limit, "offset": offset}
            ).fetchall()
            return [
                Book(
                    id=r[0],
                    title=r[1],
                    author=r[2],
                    source_path=r[3],
                    content_hash=r[4],
                    total_chapters=r[5],
                    total_sentences=r[6],
                    total_words=r[7],
                    created_at=r[8],
                    updated_at=r[9],
                )
                for r in rows
            ]

    def delete_book(self, book_id: int) -> bool:
        """Delete a book and all dependent rows. Returns False if the book does not exist."""
        with self.engine.begin() as conn:
            params = {"id": book_id}
            if conn.execute(text("SELECT 1 FROM books WHERE id = :id"), params).fetchone() is None:
                return False
            # Explicit order: do not rely on FK cascade (SQLite has it disabled by default).
            conn.execute(text("DELETE FROM network_metrics WHERE session_id IN (SELECT id FROM reading_sessions WHERE book_id = :id)"), params)
            for table in ("reading_sessions", "bookmarks", "audio_notes", "book_sentences"):
                conn.execute(text(f"DELETE FROM {table} WHERE book_id = :id"), params)  # noqa: S608
            conn.execute(text("DELETE FROM books WHERE id = :id"), params)
            return True

    def get_sentences(self, book_id: int, start_idx: int = 0, limit: int = 100) -> list[BookSentence]:
        """Fetch slice of sequential sentences for a book."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT id, book_id, chapter_index, sentence_index, text_content, word_count, content_hash, cached_audio_path
                    FROM book_sentences
                    WHERE book_id = :book_id AND sentence_index >= :start_idx
                    ORDER BY sentence_index ASC
                    LIMIT :limit
                """),
                {"book_id": book_id, "start_idx": start_idx, "limit": limit}
            ).fetchall()
            return [
                BookSentence(
                    id=r[0],
                    book_id=r[1],
                    chapter_index=r[2],
                    sentence_index=r[3],
                    text_content=r[4],
                    word_count=r[5],
                    content_hash=r[6],
                    cached_audio_path=r[7],
                )
                for r in rows
            ]


class SqlBookmarkRepository:
    """Manages persistent reading position bookmarks."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def get_bookmark(self, book_id: int) -> Bookmark | None:
        """Get current bookmark for a book."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, book_id, current_chapter, current_sentence_index, completion_percentage, last_read_at FROM bookmarks WHERE book_id = :book_id"),
                {"book_id": book_id}
            ).fetchone()
            if not row:
                return None
            return Bookmark(
                id=row[0],
                book_id=row[1],
                current_chapter=row[2],
                current_sentence_index=row[3],
                completion_percentage=row[4],
                last_read_at=row[5],
            )

    def update_bookmark(self, book_id: int, chapter_idx: int, sentence_idx: int, percentage: float) -> None:
        """Update or insert bookmark position."""
        with self.engine.begin() as conn:
            now_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            # Try update first
            update_sql = text("""
                UPDATE bookmarks
                SET current_chapter = :chapter_idx,
                    current_sentence_index = :sentence_idx,
                    completion_percentage = :percentage,
                    last_read_at = :last_read_at
                WHERE book_id = :book_id
            """)
            result = conn.execute(update_sql, {
                "book_id": book_id,
                "chapter_idx": chapter_idx,
                "sentence_idx": sentence_idx,
                "percentage": percentage,
                "last_read_at": now_str,
            })
            if result.rowcount == 0:
                insert_sql = text("""
                    INSERT INTO bookmarks (book_id, current_chapter, current_sentence_index, completion_percentage, last_read_at)
                    VALUES (:book_id, :chapter_idx, :sentence_idx, :percentage, :last_read_at)
                """)
                conn.execute(insert_sql, {
                    "book_id": book_id,
                    "chapter_idx": chapter_idx,
                    "sentence_idx": sentence_idx,
                    "percentage": percentage,
                    "last_read_at": now_str,
                })


class SqlSessionRepository:
    """Manages recorded reading sessions."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def record_session(self, session: ReadingSession) -> int:
        """Persist a completed reading session. Returns session_id."""
        with self.engine.begin() as conn:
            sql = text("""
                INSERT INTO reading_sessions (book_id, start_time, end_time, duration_seconds, sentences_read, words_read)
                VALUES (:book_id, :start_time, :end_time, :duration_seconds, :sentences_read, :words_read)
            """)
            start_str = session.start_time.strftime("%Y-%m-%d %H:%M:%S")
            end_str = session.end_time.strftime("%Y-%m-%d %H:%M:%S")
            result = conn.execute(sql, {
                "book_id": session.book_id,
                "start_time": start_str,
                "end_time": end_str,
                "duration_seconds": session.duration_seconds,
                "sentences_read": session.sentences_read,
                "words_read": session.words_read,
            })
            sess_id = result.lastrowid
            if sess_id is None:
                sess_id = conn.execute(text("SELECT last_insert_rowid()")).scalar()
            session.id = sess_id
            return sess_id

    def get_recent_sessions(self, book_id: int | None = None, days: int = 7) -> list[ReadingSession]:
        """Query reading sessions within the past N days."""
        with self.engine.connect() as conn:
            query = "SELECT id, book_id, start_time, end_time, duration_seconds, sentences_read, words_read, created_at FROM reading_sessions"
            params: dict[str, Any] = {}
            if book_id is not None:
                query += " WHERE book_id = :book_id"
                params["book_id"] = book_id
            query += " ORDER BY id DESC"

            rows = conn.execute(text(query), params).fetchall()
            return [
                ReadingSession(
                    id=r[0],
                    book_id=r[1],
                    start_time=r[2] if isinstance(r[2], datetime) else datetime.fromisoformat(str(r[2])),
                    end_time=r[3] if isinstance(r[3], datetime) else datetime.fromisoformat(str(r[3])),
                    duration_seconds=r[4],
                    sentences_read=r[5],
                    words_read=r[6],
                    created_at=r[7],
                )
                for r in rows
            ]


    def get_daily_stats(self, days: int = 7) -> list[dict[str, Any]]:
        """Return one row per calendar day for the last `days` days (zero-filled)."""
        days = max(1, days)
        today = datetime.now(UTC).date()
        first_day = today - timedelta(days=days - 1)
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT DATE(start_time), SUM(duration_seconds), SUM(words_read), COUNT(id)
                    FROM reading_sessions
                    WHERE start_time >= :since
                    GROUP BY DATE(start_time)
                """),
                {"since": first_day.strftime("%Y-%m-%d 00:00:00")},
            ).fetchall()
        by_day = {str(r[0]): r for r in rows}
        result = []
        for offset in range(days):
            day = (first_day + timedelta(days=offset)).isoformat()
            r = by_day.get(day)
            result.append({
                "date": day,
                "minutes": round(float(r[1] or 0) / 60.0, 1) if r else 0.0,
                "words": int(r[2] or 0) if r else 0,
                "sessions": int(r[3] or 0) if r else 0,
            })
        return result


class SqlTelemetryRepository:
    """Manages operational network and synthesis telemetry metrics."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def log_metrics(self, metrics: list[NetworkMetric]) -> None:
        """Batch insert sentence-level synthesis and latency telemetry."""
        if not metrics:
            return
        with self.engine.begin() as conn:
            sql = text("""
                INSERT INTO network_metrics (session_id, sentence_index, response_time_seconds, lan_ping_ms, tailscale_ping_ms, status)
                VALUES (:session_id, :sentence_index, :response_time_seconds, :lan_ping_ms, :tailscale_ping_ms, :status)
            """)
            params = [
                {
                    "session_id": m.session_id,
                    "sentence_index": m.sentence_index,
                    "response_time_seconds": m.response_time_seconds,
                    "lan_ping_ms": m.lan_ping_ms,
                    "tailscale_ping_ms": m.tailscale_ping_ms,
                    "status": m.status,
                }
                for m in metrics
            ]
            conn.execute(sql, params)

    def get_aggregated_metrics(self, book_id: int | None = None, days: int = 7) -> dict:
        """Return average response time, LAN latency, and Tailscale latency."""
        with self.engine.connect() as conn:
            # 1. Total listening minutes and words from reading_sessions
            sess_sql = "SELECT SUM(duration_seconds), SUM(words_read), COUNT(id) FROM reading_sessions"
            sess_params: dict[str, Any] = {}
            if book_id is not None:
                sess_sql += " WHERE book_id = :book_id"
                sess_params["book_id"] = book_id

            sess_row = conn.execute(text(sess_sql), sess_params).fetchone()
            # MySQL returns Decimal for SUM(); normalise so arithmetic with floats works.
            total_duration_sec = float(sess_row[0] or 0) if sess_row else 0.0
            total_words = int(sess_row[1] or 0) if sess_row else 0
            total_sessions = int(sess_row[2] or 0) if sess_row else 0

            # 2. Avg response time, LAN, Tailscale pings from network_metrics
            metric_sql = """
                SELECT AVG(nm.response_time_seconds), AVG(nm.lan_ping_ms), AVG(nm.tailscale_ping_ms)
                FROM network_metrics nm
            """
            metric_params: dict[str, Any] = {}
            if book_id is not None:
                metric_sql += " JOIN reading_sessions rs ON nm.session_id = rs.id WHERE rs.book_id = :book_id"
                metric_params["book_id"] = book_id

            metric_row = conn.execute(text(metric_sql), metric_params).fetchone()
            avg_resp = float(metric_row[0] or 0.0) if metric_row else 0.0
            avg_lan = float(metric_row[1] or 0.0) if metric_row else 0.0
            avg_tailscale = float(metric_row[2] or 0.0) if metric_row else 0.0

            return {
                "total_listening_minutes": round(total_duration_sec / 60.0, 1),
                "total_words_absorbed": int(total_words),
                "total_sessions": int(total_sessions),
                "avg_sentence_response_time_sec": round(avg_resp, 3),
                "avg_lan_ping_ms": round(avg_lan, 1),
                "avg_tailscale_ping_ms": round(avg_tailscale, 1),
            }

    def get_latency_stats(self, days: int = 7) -> dict[str, Any]:
        """Return latency (ms) avg/p95/max and success rate from network_metrics."""
        since = (datetime.now(UTC) - timedelta(days=max(1, days))).strftime("%Y-%m-%d %H:%M:%S")
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT response_time_seconds, status FROM network_metrics WHERE recorded_at >= :since"),
                {"since": since},
            ).fetchall()
        latencies = sorted(float(r[0]) * 1000.0 for r in rows)
        total = len(rows)
        ok = sum(1 for r in rows if str(r[1]).upper() == "SUCCESS")
        if not latencies:
            return {"total_calls": 0, "avg_latency_ms": 0.0, "p95_latency_ms": 0.0, "max_latency_ms": 0.0, "success_rate": 0.0}
        p95_index = min(len(latencies) - 1, max(0, int(round(0.95 * len(latencies))) - 1))
        return {
            "total_calls": total,
            "avg_latency_ms": round(sum(latencies) / len(latencies), 1),
            "p95_latency_ms": round(latencies[p95_index], 1),
            "max_latency_ms": round(latencies[-1], 1),
            "success_rate": round(ok / total * 100.0, 1),
        }


class SqlVoiceRepository:
    """Persists custom (cloned) voice profiles."""

    _COLS = "voice_id, provider, display_name, language, gender, style, is_custom, sample_path, consent_at"

    def __init__(self, engine: Engine):
        self.engine = engine

    @staticmethod
    def _row(r: Any) -> dict[str, Any]:
        return {
            "voice_id": r[0], "provider": r[1], "display_name": r[2], "language": r[3],
            "gender": r[4], "style": r[5], "is_custom": bool(r[6]), "sample_path": r[7],
            "consent_at": str(r[8]) if r[8] else None,
        }

    def add_voice(self, voice_id: str, provider: str, display_name: str, language: str,
                  gender: str | None, sample_path: str | None, consent_at: datetime) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO voice_profiles (voice_id, provider, display_name, language, gender, is_custom, sample_path, consent_at)
                    VALUES (:voice_id, :provider, :display_name, :language, :gender, 1, :sample_path, :consent_at)
                """),
                {"voice_id": voice_id, "provider": provider, "display_name": display_name,
                 "language": language, "gender": gender, "sample_path": sample_path,
                 "consent_at": consent_at.strftime("%Y-%m-%d %H:%M:%S")},
            )

    def list_voices(self) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(f"SELECT {self._COLS} FROM voice_profiles ORDER BY id DESC")).fetchall()  # noqa: S608
        return [self._row(r) for r in rows]

    def get_voice(self, voice_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            r = conn.execute(
                text(f"SELECT {self._COLS} FROM voice_profiles WHERE voice_id = :v"), {"v": voice_id}  # noqa: S608
            ).fetchone()
        return self._row(r) if r else None

    def delete_voice(self, voice_id: str) -> bool:
        with self.engine.begin() as conn:
            return conn.execute(text("DELETE FROM voice_profiles WHERE voice_id = :v"), {"v": voice_id}).rowcount > 0


class SqlNoteRepository:
    """Persists audio notes (highlighted excerpt + user note)."""

    _SELECT = """
        SELECT n.id, n.book_id, b.title, n.sentence_index, n.start_offset, n.end_offset, n.note_text, n.created_at
        FROM audio_notes n JOIN books b ON b.id = n.book_id
    """

    def __init__(self, engine: Engine):
        self.engine = engine

    @staticmethod
    def _row(r: Any) -> dict[str, Any]:
        return {
            "id": r[0], "book_id": r[1], "book_title": r[2], "sentence_index": r[3],
            "start_offset": r[4], "end_offset": r[5], "note_text": r[6],
            "created_at": r[7].isoformat() if isinstance(r[7], datetime) else str(r[7]),
        }

    def create_note(self, book_id: int, sentence_index: int, start_offset: int, end_offset: int, note_text: str) -> int:
        with self.engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO audio_notes (book_id, sentence_index, start_offset, end_offset, note_text)
                    VALUES (:book_id, :sentence_index, :start_offset, :end_offset, :note_text)
                """),
                {"book_id": book_id, "sentence_index": sentence_index, "start_offset": start_offset,
                 "end_offset": end_offset, "note_text": note_text},
            )
            note_id = result.lastrowid
            if note_id is None:
                note_id = conn.execute(text("SELECT last_insert_rowid()")).scalar()
            return int(note_id)

    def get_note(self, note_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            r = conn.execute(text(self._SELECT + " WHERE n.id = :id"), {"id": note_id}).fetchone()
        return self._row(r) if r else None

    def list_notes(self, book_id: int | None = None) -> list[dict[str, Any]]:
        sql, params = self._SELECT, {}
        if book_id is not None:
            sql += " WHERE n.book_id = :book_id"
            params["book_id"] = book_id
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql + " ORDER BY n.id DESC"), params).fetchall()
        return [self._row(r) for r in rows]

    def update_note_text(self, note_id: int, note_text: str) -> bool:
        with self.engine.begin() as conn:
            return conn.execute(
                text("UPDATE audio_notes SET note_text = :t WHERE id = :id"), {"t": note_text, "id": note_id}
            ).rowcount > 0

    def delete_note(self, note_id: int) -> bool:
        with self.engine.begin() as conn:
            return conn.execute(text("DELETE FROM audio_notes WHERE id = :id"), {"id": note_id}).rowcount > 0


class SqlSettingsRepository:
    """Key/value application settings and daily character usage counters."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def get(self, key: str, default: str | None = None) -> str | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT setting_value FROM app_settings WHERE setting_key = :k"), {"k": key}
            ).fetchone()
        return row[0] if row else default

    def set(self, key: str, value: str) -> None:
        with self.engine.begin() as conn:
            updated = conn.execute(
                text("UPDATE app_settings SET setting_value = :v WHERE setting_key = :k"), {"k": key, "v": value}
            ).rowcount
            if updated == 0:
                conn.execute(
                    text("INSERT INTO app_settings (setting_key, setting_value) VALUES (:k, :v)"), {"k": key, "v": value}
                )

    @staticmethod
    def _usage_key(day: datetime | None = None) -> str:
        return f"chars_used:{(day or datetime.now(UTC)).strftime('%Y-%m-%d')}"

    def chars_used_today(self) -> int:
        return int(self.get(self._usage_key(), "0") or 0)

    def add_chars_used(self, count: int) -> None:
        self.set(self._usage_key(), str(self.chars_used_today() + max(0, count)))
