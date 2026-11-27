"""Parameterized SQL repository implementations for books, bookmarks, sessions, and telemetry."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Engine, text

from src.core.models.book import Book, Bookmark, BookSentence, Chapter
from src.core.models.session import ReadingSession
from src.core.models.telemetry import NetworkMetric
from src.core.text_search import normalize_search, search_tokens

logger = logging.getLogger(__name__)


_INSERT_CHAPTER = """
    INSERT INTO document_chapters (book_id, chapter_index, title, start_sentence_index, end_sentence_index)
    VALUES (:book_id, :chapter_index, :title, :start, :end)
"""


class SqlBookRepository:
    """Manages persistence and retrieval for books and sentences."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def save_book(self, book: Book, sentences: list[BookSentence], chapters: list[Chapter] | None = None) -> int:
        """Insert book, sentences and chapters atomically within a transaction. Returns book_id."""
        with self.engine.begin() as conn:
            # 1. Insert book
            insert_book_sql = text("""
                INSERT INTO books (title, author, source_path, content_hash, total_chapters, total_sentences, total_words, owner_id, is_public,
                                   category_id, cover_path, search_text)
                VALUES (:title, :author, :source_path, :content_hash, :total_chapters, :total_sentences, :total_words, :owner_id, :is_public,
                        :category_id, :cover_path, :search_text)
            """)
            result = conn.execute(insert_book_sql, {
                "title": book.title,
                "author": book.author,
                "source_path": book.source_path,
                "content_hash": book.content_hash,
                "total_chapters": book.total_chapters,
                "total_sentences": book.total_sentences,
                "total_words": book.total_words,
                "owner_id": book.owner_id,
                "is_public": 1 if book.is_public else 0,
                "category_id": book.category_id,
                "cover_path": book.cover_path,
                "search_text": book.search_text or normalize_search(f"{book.title} {book.author}")[:600],
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

            if chapters:
                conn.execute(text(_INSERT_CHAPTER), [
                    {"book_id": book_id, "chapter_index": c.chapter_index, "title": c.title[:255],
                     "start": c.start_sentence_index, "end": c.end_sentence_index}
                    for c in chapters
                ])

            book.id = book_id
            return book_id

    _BOOK_COLS = (
        "id, title, author, source_path, content_hash, total_chapters, total_sentences, total_words, "
        "created_at, updated_at, owner_id, is_public, category_id, cover_path, search_text"
    )

    @staticmethod
    def _book(r: Any) -> Book:
        return Book(
            id=r[0], title=r[1], author=r[2], source_path=r[3], content_hash=r[4], total_chapters=r[5],
            total_sentences=r[6], total_words=r[7], created_at=r[8], updated_at=r[9],
            owner_id=r[10], is_public=bool(r[11]), category_id=r[12], cover_path=r[13], search_text=r[14],
        )

    def get_by_id(self, book_id: int) -> Book | None:
        """Fetch book by surrogate ID. No access check: routes use `get_visible`."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT {self._BOOK_COLS} FROM books WHERE id = :id"), {"id": book_id}  # noqa: S608
            ).fetchone()
        return self._book(row) if row else None

    def get_book(self, book_id: int) -> Book | None:
        """Alias for get_by_id."""
        return self.get_by_id(book_id)

    def get_visible(self, book_id: int, user_id: int) -> Book | None:
        """The book if `user_id` may see it (own book or public), else None, so a stranger's book looks missing."""
        book = self.get_by_id(book_id)
        return book if book and book.can_view(user_id) else None

    def get_book_sentences(self, book_id: int) -> list[BookSentence]:
        """Fetch all sentences for a book."""
        return self.get_sentences(book_id, start_idx=0, limit=100000)

    def get_by_hash(self, content_hash: str, owner_id: int | None) -> Book | None:
        """The book with this content among the owner's books (owner None = system books)."""
        condition = "owner_id IS NULL" if owner_id is None else "owner_id = :owner"
        with self.engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT {self._BOOK_COLS} FROM books WHERE content_hash = :hash AND {condition}"),  # noqa: S608
                {"hash": content_hash, "owner": owner_id},
            ).fetchone()
        return self._book(row) if row else None

    def list_books(self, limit: int = 50, offset: int = 0, user_id: int | None = None) -> list[Book]:
        """Books visible to `user_id` (their own plus public ones), newest first. None = every book (CLI/admin tools)."""
        where, params = "", {"limit": limit, "offset": offset}
        if user_id is not None:
            where, params["user"] = "WHERE owner_id = :user OR is_public = 1", user_id
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(f"SELECT {self._BOOK_COLS} FROM books {where} ORDER BY id DESC LIMIT :limit OFFSET :offset"),  # noqa: S608
                params,
            ).fetchall()
        return [self._book(r) for r in rows]

    def set_public(self, book_id: int, is_public: bool) -> None:
        """Publish a book as a system book (owner None) or take it back; only admins reach this."""
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE books SET is_public = :p WHERE id = :id"), {"p": 1 if is_public else 0, "id": book_id})

    def list_public_with_shelves(self) -> list[tuple[Book, int]]:
        """Every public book with the number of shelves it is on (admin catalogue; no private data)."""
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                f"SELECT {self._BOOK_COLS}, "  # noqa: S608
                "(SELECT COUNT(*) FROM user_book_progress p WHERE p.book_id = books.id) "
                "FROM books WHERE is_public = 1 ORDER BY id DESC"
            )).fetchall()
        return [(self._book(r), int(r[15] or 0)) for r in rows]

    def rename_book(self, book_id: int, title: str) -> bool:
        """Change a book's title. Returns False if the book does not exist."""
        with self.engine.begin() as conn:
            if conn.execute(text("SELECT 1 FROM books WHERE id = :id"), {"id": book_id}).fetchone() is None:
                return False
            author = conn.execute(text("SELECT author FROM books WHERE id = :id"), {"id": book_id}).scalar() or ""
            conn.execute(
                text("UPDATE books SET title = :title, search_text = :search, updated_at = :now WHERE id = :id"),
                {"title": title, "search": normalize_search(f"{title} {author}")[:600], "id": book_id,
                 "now": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")},
            )
            return True

    def update_text(self, book_id: int, title: str | None = None, author: str | None = None) -> bool:
        """Change a book's title and/or author (the search text follows). False if the book does not exist."""
        with self.engine.begin() as conn:
            row = conn.execute(text("SELECT title, author FROM books WHERE id = :id"), {"id": book_id}).fetchone()
            if row is None:
                return False
            new_title = row[0] if title is None else title
            new_author = row[1] if author is None else author
            conn.execute(
                text("UPDATE books SET title = :t, author = :a, search_text = :s, updated_at = :now WHERE id = :id"),
                {"t": new_title, "a": new_author, "s": normalize_search(f"{new_title} {new_author}")[:600], "id": book_id,
                 "now": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")},
            )
            return True

    def set_category(self, book_id: int, category_id: int | None) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE books SET category_id = :c WHERE id = :id"), {"c": category_id, "id": book_id})

    def set_cover(self, book_id: int, cover_path: str | None) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE books SET cover_path = :c WHERE id = :id"), {"c": cover_path, "id": book_id})

    def delete_book(self, book_id: int) -> bool:
        """Delete a book and all dependent rows. Returns False if the book does not exist."""
        with self.engine.begin() as conn:
            params = {"id": book_id}
            if conn.execute(text("SELECT 1 FROM books WHERE id = :id"), params).fetchone() is None:
                return False
            # Explicit order: do not rely on FK cascade (SQLite has it disabled by default).
            conn.execute(text("DELETE FROM network_metrics WHERE session_id IN (SELECT id FROM reading_sessions WHERE book_id = :id)"), params)
            for table in ("reading_sessions", "bookmarks", "user_book_progress", "audio_notes", "document_chapters", "book_sentences"):
                conn.execute(text(f"DELETE FROM {table} WHERE book_id = :id"), params)  # noqa: S608
            conn.execute(text("DELETE FROM books WHERE id = :id"), params)
            return True

    def get_chapters(self, book_id: int) -> list[Chapter]:
        """Chapters of a book in order. Books ingested before chapter titles were stored get them rebuilt
        from the sentences' chapter numbers ("Chương N"); the result is saved for next time."""
        chapters = self._load_chapters(book_id)
        if chapters or not self.get_by_id(book_id):
            return chapters
        with self.engine.begin() as conn:
            rows = conn.execute(
                text("""
                    SELECT chapter_index, MIN(sentence_index), MAX(sentence_index)
                    FROM book_sentences WHERE book_id = :id GROUP BY chapter_index ORDER BY chapter_index
                """),
                {"id": book_id},
            ).fetchall()
            if not rows:
                return []
            rebuilt = [
                {"book_id": book_id, "chapter_index": int(r[0]), "title": f"Chương {int(r[0])}",
                 "start": int(r[1]), "end": int(r[2])}
                for r in rows
            ]
            conn.execute(text(_INSERT_CHAPTER), rebuilt)
        return self._load_chapters(book_id)

    def _load_chapters(self, book_id: int) -> list[Chapter]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT c.chapter_index, c.title, c.start_sentence_index, c.end_sentence_index,
                           (SELECT COALESCE(SUM(s.word_count), 0) FROM book_sentences s
                            WHERE s.book_id = c.book_id AND s.sentence_index BETWEEN c.start_sentence_index AND c.end_sentence_index)
                    FROM document_chapters c WHERE c.book_id = :id ORDER BY c.chapter_index
                """),
                {"id": book_id},
            ).fetchall()
        return [Chapter(int(r[0]), r[1], int(r[2]), int(r[3]), int(r[4] or 0)) for r in rows]

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
    """Reading position of ONE user in each book (table user_book_progress)."""

    def __init__(self, engine: Engine, user_id: int):
        self.engine = engine
        self.user_id = user_id

    def get_bookmark(self, book_id: int) -> Bookmark | None:
        """This user's bookmark for a book, or None if they never opened it."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT book_id, current_chapter, current_sentence_index, completion_percentage, last_read_at, voice
                    FROM user_book_progress WHERE user_id = :user AND book_id = :book_id
                """),
                {"user": self.user_id, "book_id": book_id},
            ).fetchone()
        if not row:
            return None
        return Bookmark(
            book_id=row[0], current_chapter=row[1], current_sentence_index=row[2],
            completion_percentage=row[3], last_read_at=row[4], voice=row[5],
        )

    def update_bookmark(
        self, book_id: int, chapter_idx: int, sentence_idx: int, percentage: float, voice: str | None = None
    ) -> None:
        """Update or insert the position. `voice=None` keeps the voice remembered earlier."""
        params = {
            "user": self.user_id, "book_id": book_id, "chapter_idx": chapter_idx, "sentence_idx": sentence_idx,
            "percentage": percentage, "voice": voice, "status": "completed" if percentage >= 100 else "reading",
            "last_read_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
        }
        with self.engine.begin() as conn:
            updated = conn.execute(
                text("""
                    UPDATE user_book_progress
                    SET current_chapter = :chapter_idx, current_sentence_index = :sentence_idx,
                        completion_percentage = :percentage, last_read_at = :last_read_at, status = :status,
                        voice = COALESCE(:voice, voice)
                    WHERE user_id = :user AND book_id = :book_id
                """),
                params,
            ).rowcount
            if updated == 0:
                conn.execute(
                    text("""
                        INSERT INTO user_book_progress
                            (user_id, book_id, status, current_chapter, current_sentence_index, completion_percentage, voice, last_read_at)
                        VALUES (:user, :book_id, :status, :chapter_idx, :sentence_idx, :percentage, :voice, :last_read_at)
                    """),
                    params,
                )

    def bookmarks_by_book(self) -> dict[int, Bookmark]:
        """All of this user's bookmarks (for the library list)."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT book_id, current_chapter, current_sentence_index, completion_percentage, last_read_at, voice
                    FROM user_book_progress WHERE user_id = :user
                """),
                {"user": self.user_id},
            ).fetchall()
        return {
            r[0]: Bookmark(book_id=r[0], current_chapter=r[1], current_sentence_index=r[2],
                           completion_percentage=r[3], last_read_at=r[4], voice=r[5])
            for r in rows
        }


class SqlSessionRepository:
    """One user's recorded reading sessions (every query is limited to `user_id`)."""

    def __init__(self, engine: Engine, user_id: int):
        self.engine = engine
        self.user_id = user_id

    def record_session(self, session: ReadingSession) -> int:
        """Persist a completed reading session. Returns session_id."""
        with self.engine.begin() as conn:
            sql = text("""
                INSERT INTO reading_sessions (user_id, book_id, start_time, end_time, duration_seconds, sentences_read, words_read, voice)
                VALUES (:user_id, :book_id, :start_time, :end_time, :duration_seconds, :sentences_read, :words_read, :voice)
            """)
            start_str = session.start_time.strftime("%Y-%m-%d %H:%M:%S")
            end_str = session.end_time.strftime("%Y-%m-%d %H:%M:%S")
            result = conn.execute(sql, {
                "user_id": self.user_id,
                "book_id": session.book_id,
                "start_time": start_str,
                "end_time": end_str,
                "duration_seconds": session.duration_seconds,
                "sentences_read": session.sentences_read,
                "words_read": session.words_read,
                "voice": session.voice,
            })
            sess_id = result.lastrowid
            if sess_id is None:
                sess_id = conn.execute(text("SELECT last_insert_rowid()")).scalar()
            session.id = sess_id
            return sess_id

    def get_recent_sessions(self, book_id: int | None = None, days: int = 7) -> list[ReadingSession]:
        """Query reading sessions within the past N days."""
        with self.engine.connect() as conn:
            query = "SELECT id, book_id, start_time, end_time, duration_seconds, sentences_read, words_read, created_at FROM reading_sessions WHERE user_id = :user"
            params: dict[str, Any] = {"user": self.user_id}
            if book_id is not None:
                query += " AND book_id = :book_id"
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


    def get_voice_stats(self, days: int = 7) -> list[dict[str, Any]]:
        """Listening time per voice over the last `days` days; sessions without a voice are 'unknown'."""
        first_day = datetime.now(UTC).date() - timedelta(days=max(1, days) - 1)
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT voice, SUM(duration_seconds), SUM(words_read), COUNT(id)
                    FROM reading_sessions
                    WHERE user_id = :user AND start_time >= :since
                    GROUP BY voice
                """),
                {"user": self.user_id, "since": first_day.strftime("%Y-%m-%d 00:00:00")},
            ).fetchall()
        stats = [
            {"voice": r[0] or "", "minutes": round(float(r[1] or 0) / 60.0, 1),
             "words": int(r[2] or 0), "sessions": int(r[3] or 0)}
            for r in rows
        ]
        return sorted(stats, key=lambda s: s["minutes"], reverse=True)

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
                    WHERE user_id = :user AND start_time >= :since
                    GROUP BY DATE(start_time)
                """),
                {"user": self.user_id, "since": first_day.strftime("%Y-%m-%d 00:00:00")},
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
    """Operational network and synthesis telemetry. With `user_id`, statistics cover that user's sessions only."""

    def __init__(self, engine: Engine, user_id: int | None = None):
        self.engine = engine
        self.user_id = user_id

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
            sess_sql = "SELECT SUM(duration_seconds), SUM(words_read), COUNT(id) FROM reading_sessions WHERE 1 = 1"
            sess_params: dict[str, Any] = {}
            if self.user_id is not None:
                sess_sql += " AND user_id = :user"
                sess_params["user"] = self.user_id
            if book_id is not None:
                sess_sql += " AND book_id = :book_id"
                sess_params["book_id"] = book_id

            sess_row = conn.execute(text(sess_sql), sess_params).fetchone()
            # MySQL returns Decimal for SUM(); normalise so arithmetic with floats works.
            total_duration_sec = float(sess_row[0] or 0) if sess_row else 0.0
            total_words = int(sess_row[1] or 0) if sess_row else 0
            total_sessions = int(sess_row[2] or 0) if sess_row else 0

            # 2. Avg response time, LAN, Tailscale pings from network_metrics
            metric_sql = """
                SELECT AVG(nm.response_time_seconds), AVG(nm.lan_ping_ms), AVG(nm.tailscale_ping_ms)
                FROM network_metrics nm JOIN reading_sessions rs ON nm.session_id = rs.id WHERE 1 = 1
            """
            metric_params: dict[str, Any] = {}
            if self.user_id is not None:
                metric_sql += " AND rs.user_id = :user"
                metric_params["user"] = self.user_id
            if book_id is not None:
                metric_sql += " AND rs.book_id = :book_id"
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
            user_filter = " AND rs.user_id = :user" if self.user_id is not None else ""
            rows = conn.execute(
                text("SELECT nm.response_time_seconds, nm.status FROM network_metrics nm "  # noqa: S608
                     "JOIN reading_sessions rs ON nm.session_id = rs.id "
                     f"WHERE nm.recorded_at >= :since{user_filter}"),
                {"since": since, "user": self.user_id},
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
    """Custom (cloned) voice profiles. A voice belongs to its owner; public voices are shared by everyone."""

    _COLS = "voice_id, provider, display_name, language, gender, style, is_custom, sample_path, consent_at, owner_id, is_public"

    def __init__(self, engine: Engine):
        self.engine = engine

    @staticmethod
    def _row(r: Any) -> dict[str, Any]:
        return {
            "voice_id": r[0], "provider": r[1], "display_name": r[2], "language": r[3],
            "gender": r[4], "style": r[5], "is_custom": bool(r[6]), "sample_path": r[7],
            "consent_at": str(r[8]) if r[8] else None, "owner_id": r[9], "is_public": bool(r[10]),
        }

    def add_voice(self, voice_id: str, provider: str, display_name: str, language: str,
                  gender: str | None, sample_path: str | None, consent_at: datetime,
                  owner_id: int | None = None, is_public: bool = False) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO voice_profiles (voice_id, provider, display_name, language, gender, is_custom, sample_path, consent_at, owner_id, is_public)
                    VALUES (:voice_id, :provider, :display_name, :language, :gender, 1, :sample_path, :consent_at, :owner_id, :is_public)
                """),
                {"voice_id": voice_id, "provider": provider, "display_name": display_name,
                 "language": language, "gender": gender, "sample_path": sample_path,
                 "consent_at": consent_at.strftime("%Y-%m-%d %H:%M:%S"),
                 "owner_id": owner_id, "is_public": 1 if is_public else 0},
            )

    def list_voices(self, user_id: int | None = None) -> list[dict[str, Any]]:
        """Voices visible to `user_id` (their own and public ones); None = all of them (admin tools)."""
        where, params = "", {}
        if user_id is not None:
            where, params = "WHERE owner_id = :user OR is_public = 1", {"user": user_id}
        with self.engine.connect() as conn:
            rows = conn.execute(text(f"SELECT {self._COLS} FROM voice_profiles {where} ORDER BY id DESC"), params).fetchall()  # noqa: S608
        return [self._row(r) for r in rows]

    def count_owned(self, user_id: int) -> int:
        with self.engine.connect() as conn:
            return int(conn.execute(
                text("SELECT COUNT(*) FROM voice_profiles WHERE owner_id = :u"), {"u": user_id}
            ).scalar() or 0)

    def get_voice(self, voice_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            r = conn.execute(
                text(f"SELECT {self._COLS} FROM voice_profiles WHERE voice_id = :v"), {"v": voice_id}  # noqa: S608
            ).fetchone()
        return self._row(r) if r else None

    def delete_voice(self, voice_id: str) -> bool:
        with self.engine.begin() as conn:
            return conn.execute(text("DELETE FROM voice_profiles WHERE voice_id = :v"), {"v": voice_id}).rowcount > 0

    def set_public(self, voice_id: str, is_public: bool) -> None:
        """Share a voice with everyone (system voice) or take it back."""
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE voice_profiles SET is_public = :p WHERE voice_id = :v"),
                         {"p": 1 if is_public else 0, "v": voice_id})

    def rename_voice(self, voice_id: str, display_name: str) -> bool:
        with self.engine.begin() as conn:
            return conn.execute(text("UPDATE voice_profiles SET display_name = :n WHERE voice_id = :v"),
                                {"n": display_name, "v": voice_id}).rowcount > 0


class _Unset:
    """Marks "the caller did not say" (None is a real value: it clears the tag)."""


UNSET = _Unset()


class SqlNoteRepository:
    """One user's favourite quotes: a highlighted excerpt or a whole sentence, with the user's own note,
    a feeling tag, the sentences around it and the path of its saved audio."""

    _SELECT = """
        SELECT n.id, n.book_id, b.title, n.sentence_index, n.start_offset, n.end_offset, n.note_text, n.created_at,
               n.emotion_tag, n.context_before, n.context_after, n.audio_path, n.voice
        FROM audio_notes n JOIN books b ON b.id = n.book_id
    """

    def __init__(self, engine: Engine, user_id: int):
        self.engine = engine
        self.user_id = user_id

    @staticmethod
    def _row(r: Any) -> dict[str, Any]:
        return {
            "id": r[0], "book_id": r[1], "book_title": r[2], "sentence_index": r[3],
            "start_offset": r[4], "end_offset": r[5], "note_text": r[6],
            "created_at": r[7].isoformat() if isinstance(r[7], datetime) else str(r[7]),
            "emotion_tag": r[8], "context_before": r[9] or "", "context_after": r[10] or "",
            "audio_path": r[11], "voice": r[12],
        }

    def create_note(self, book_id: int, sentence_index: int, start_offset: int, end_offset: int, note_text: str,
                    emotion_tag: str | None = None, context_before: str = "", context_after: str = "",
                    voice: str | None = None) -> int:
        with self.engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO audio_notes (user_id, book_id, sentence_index, start_offset, end_offset, note_text,
                                             emotion_tag, context_before, context_after, voice)
                    VALUES (:user_id, :book_id, :sentence_index, :start_offset, :end_offset, :note_text,
                            :emotion_tag, :before, :after, :voice)
                """),
                {"user_id": self.user_id, "book_id": book_id, "sentence_index": sentence_index,
                 "start_offset": start_offset, "end_offset": end_offset, "note_text": note_text,
                 "emotion_tag": emotion_tag, "before": context_before, "after": context_after, "voice": voice},
            )
            note_id = result.lastrowid
            if note_id is None:
                note_id = conn.execute(text("SELECT last_insert_rowid()")).scalar()
            return int(note_id)

    def find_same(self, book_id: int, sentence_index: int, start_offset: int, end_offset: int) -> dict[str, Any] | None:
        """This user's quote of exactly this passage, if any (one tap twice must not save it twice)."""
        with self.engine.connect() as conn:
            r = conn.execute(
                text(self._SELECT + " WHERE n.user_id = :user AND n.book_id = :b AND n.sentence_index = :i "
                                    "AND n.start_offset = :s AND n.end_offset = :e ORDER BY n.id LIMIT 1"),
                {"user": self.user_id, "b": book_id, "i": sentence_index, "s": start_offset, "e": end_offset},
            ).fetchone()
        return self._row(r) if r else None

    def get_note(self, note_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            r = conn.execute(
                text(self._SELECT + " WHERE n.id = :id AND n.user_id = :user"), {"id": note_id, "user": self.user_id}
            ).fetchone()
        return self._row(r) if r else None

    def list_notes(self, book_id: int | None = None, emotion_tag: str | None = None) -> list[dict[str, Any]]:
        sql = self._SELECT + " WHERE n.user_id = :user"
        params: dict[str, Any] = {"user": self.user_id}
        if book_id is not None:
            sql += " AND n.book_id = :book_id"
            params["book_id"] = book_id
        if emotion_tag is not None:
            sql += " AND n.emotion_tag = :tag"
            params["tag"] = emotion_tag
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql + " ORDER BY n.id DESC"), params).fetchall()
        return [self._row(r) for r in rows]

    def update_note(self, note_id: int, note_text: str | None = None, emotion_tag: str | None | _Unset = UNSET) -> bool:
        """Change the text and/or the feeling; what is not given stays. `emotion_tag=None` clears the tag."""
        sets: list[str] = []
        params: dict[str, Any] = {"id": note_id, "user": self.user_id}
        if note_text is not None:
            sets.append("note_text = :t")
            params["t"] = note_text
        if not isinstance(emotion_tag, _Unset):
            sets.append("emotion_tag = :tag")
            params["tag"] = emotion_tag
        if not sets:
            return self.get_note(note_id) is not None
        with self.engine.begin() as conn:
            return conn.execute(
                text(f"UPDATE audio_notes SET {', '.join(sets)} WHERE id = :id AND user_id = :user"), params  # noqa: S608
            ).rowcount > 0

    def update_note_text(self, note_id: int, note_text: str) -> bool:
        return self.update_note(note_id, note_text=note_text)

    def set_audio(self, note_id: int, audio_path: str | None, voice: str | None = None) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE audio_notes SET audio_path = :p, voice = COALESCE(:v, voice) WHERE id = :id AND user_id = :user"),
                {"p": audio_path, "v": voice, "id": note_id, "user": self.user_id},
            )

    def delete_note(self, note_id: int) -> bool:
        with self.engine.begin() as conn:
            return conn.execute(
                text("DELETE FROM audio_notes WHERE id = :id AND user_id = :user"), {"id": note_id, "user": self.user_id}
            ).rowcount > 0

    @staticmethod
    def audio_paths_for_book(engine: Engine, book_id: int) -> list[str]:
        """Saved audio of EVERY user's quotes of a book (used when the book is deleted, before its rows go)."""
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT audio_path FROM audio_notes WHERE book_id = :b AND audio_path IS NOT NULL"), {"b": book_id}
            ).fetchall()
        return [r[0] for r in rows]


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


class SqlUserSettingsRepository:
    """One user's preferences (default voice, speed, prefetch). System-wide settings stay in SqlSettingsRepository."""

    def __init__(self, engine: Engine, user_id: int):
        self.engine = engine
        self.user_id = user_id

    def get(self, key: str, default: str | None = None) -> str | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT setting_value FROM user_settings WHERE user_id = :u AND setting_key = :k"),
                {"u": self.user_id, "k": key},
            ).fetchone()
        return row[0] if row else default

    def set(self, key: str, value: str) -> None:
        params = {"u": self.user_id, "k": key, "v": value}
        with self.engine.begin() as conn:
            updated = conn.execute(
                text("UPDATE user_settings SET setting_value = :v WHERE user_id = :u AND setting_key = :k"), params
            ).rowcount
            if updated == 0:
                conn.execute(
                    text("INSERT INTO user_settings (user_id, setting_key, setting_value) VALUES (:u, :k, :v)"), params
                )


# ------------------------------------------------------------------------------------------ ambient sounds

class SqlAmbientRepository:
    """The library of background sounds (rain, fireplace, soft music) that administrators manage and everyone may play."""

    def __init__(self, engine: Engine):
        self.engine = engine

    @staticmethod
    def _row(r: Any) -> dict[str, Any]:
        return {"id": int(r[0]), "name": r[1], "file_name": r[2], "size_bytes": int(r[3] or 0)}

    def list_all(self) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text("SELECT id, name, file_name, size_bytes FROM ambient_tracks ORDER BY id")).fetchall()
        return [self._row(r) for r in rows]

    def get(self, track_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            r = conn.execute(
                text("SELECT id, name, file_name, size_bytes FROM ambient_tracks WHERE id = :id"), {"id": track_id}
            ).fetchone()
        return self._row(r) if r else None

    def add(self, name: str, file_name: str, size_bytes: int) -> int:
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO ambient_tracks (name, file_name, size_bytes, created_at) VALUES (:n, :f, :s, :now)"),
                {"n": name, "f": file_name, "s": size_bytes, "now": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")},
            )
            return int(conn.execute(text("SELECT id FROM ambient_tracks WHERE file_name = :f"), {"f": file_name}).scalar() or 0)

    def rename(self, track_id: int, name: str) -> bool:
        with self.engine.begin() as conn:
            return conn.execute(text("UPDATE ambient_tracks SET name = :n WHERE id = :id"), {"n": name, "id": track_id}).rowcount > 0

    def delete(self, track_id: int) -> bool:
        with self.engine.begin() as conn:
            return conn.execute(text("DELETE FROM ambient_tracks WHERE id = :id"), {"id": track_id}).rowcount > 0


# ------------------------------------------------------------------------------------------ recommendations

class SqlRecommendRepository:
    """What the recommendation engine reads: one reader's own history and the public catalogue's aggregate numbers."""

    def __init__(self, engine: Engine, user_id: int):
        self.engine = engine
        self.user_id = user_id

    @staticmethod
    def _moment(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None

    def history(self) -> list[dict[str, Any]]:
        """The reader's shelf: category, status, favourite, completion and when they last read each book."""
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT b.category_id, p.status, p.is_favorite, p.completion_percentage, p.last_read_at "
                "FROM user_book_progress p JOIN books b ON b.id = p.book_id WHERE p.user_id = :u"), {"u": self.user_id}).fetchall()
        return [{"category_id": r[0], "status": r[1], "is_favorite": bool(r[2]), "completion": float(r[3] or 0),
                 "last_read_at": self._moment(r[4])} for r in rows]

    def minutes_by_category(self) -> dict[int, float]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT b.category_id, SUM(s.duration_seconds) FROM reading_sessions s JOIN books b ON b.id = s.book_id "
                "WHERE s.user_id = :u AND b.category_id IS NOT NULL GROUP BY b.category_id"), {"u": self.user_id}).fetchall()
        return {int(r[0]): float(r[1] or 0) / 60.0 for r in rows}

    def listening_totals(self) -> tuple[int, float]:
        """(words, seconds) over all the reader's sessions: their real listening speed."""
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT COALESCE(SUM(words_read), 0), COALESCE(SUM(duration_seconds), 0) FROM reading_sessions "
                "WHERE user_id = :u"), {"u": self.user_id}).fetchone()
        return (int(row[0]), float(row[1])) if row else (0, 0.0)

    def session_count(self) -> int:
        with self.engine.connect() as conn:
            return int(conn.execute(text("SELECT COUNT(*) FROM reading_sessions WHERE user_id = :u"), {"u": self.user_id}).scalar() or 0)

    def candidates(self) -> list[tuple[Book, int]]:
        """Public books that are not yet on the reader's shelf, each with how many readers keep it (a count only)."""
        cols = ", ".join(f"b.{c.strip()}" for c in SqlBookRepository._BOOK_COLS.split(","))
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                f"SELECT {cols}, (SELECT COUNT(*) FROM user_book_progress q WHERE q.book_id = b.id) "  # noqa: S608
                "FROM books b WHERE b.is_public = 1 AND NOT EXISTS "
                "(SELECT 1 FROM user_book_progress p WHERE p.book_id = b.id AND p.user_id = :u) ORDER BY b.id DESC"),
                {"u": self.user_id}).fetchall()
        return [(SqlBookRepository._book(r), int(r[15] or 0)) for r in rows]


# ------------------------------------------------------------------------------------------ categories & shelf

class SqlCategoryRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def list_all(self) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text("SELECT id, name, slug, icon, color FROM categories ORDER BY CASE WHEN slug = 'khac' THEN 1 ELSE 0 END, sort_order, id")).fetchall()
        return [{"id": r[0], "name": r[1], "slug": r[2], "icon": r[3], "color": r[4]} for r in rows]

    def get(self, category_id: int) -> dict[str, Any] | None:
        return next((c for c in self.list_all() if c["id"] == category_id), None)

    def default_id(self) -> int | None:
        """The "Khác" category: where a book goes when nobody picked one."""
        return next((c["id"] for c in self.list_all() if c["slug"] == "khac"), None)

    def book_counts(self) -> dict[int, int]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT category_id, COUNT(*) FROM books WHERE category_id IS NOT NULL GROUP BY category_id")).fetchall()
        return {int(r[0]): int(r[1]) for r in rows}

    def create(self, name: str, slug: str, icon: str, color: str) -> int:
        with self.engine.begin() as conn:
            order = int(conn.execute(text("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM categories")).scalar() or 0)
            conn.execute(
                text("INSERT INTO categories (name, slug, icon, color, sort_order) VALUES (:n, :s, :i, :c, :o)"),
                {"n": name, "s": slug, "i": icon, "c": color, "o": order})
            return int(conn.execute(text("SELECT id FROM categories WHERE slug = :s"), {"s": slug}).scalar() or 0)

    def update(self, category_id: int, name: str, icon: str, color: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE categories SET name = :n, icon = :i, color = :c WHERE id = :id"),
                         {"n": name, "i": icon, "c": color, "id": category_id})

    def delete(self, category_id: int) -> None:
        """Remove a category; its books simply have none."""
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE books SET category_id = NULL WHERE category_id = :id"), {"id": category_id})
            conn.execute(text("DELETE FROM categories WHERE id = :id"), {"id": category_id})


@dataclass
class ShelfEntry:
    """A book as one user sees it: the book, that user's progress in it (None = never opened), and whether it is on their shelf."""
    book: Book
    progress: dict[str, Any] | None
    on_shelf: bool


SHELF_SORTS = ("recent", "title", "newest", "progress")
STATUSES = ("unread", "reading", "completed")


class SqlShelfRepository:
    """What one user sees of the library: their shelf (own books + public books they added) and the public catalogue."""

    _PROGRESS = (
        "p.status, p.is_favorite, p.current_chapter, p.current_sentence_index, "
        "p.completion_percentage, p.last_read_at, p.voice, p.user_id"
    )

    def __init__(self, engine: Engine, user_id: int):
        self.engine = engine
        self.user_id = user_id

    # -- queries -----------------------------------------------------------------------------------

    @staticmethod
    def _progress(row: Any, offset: int) -> dict[str, Any] | None:
        if row[offset + 7] is None:  # no user_book_progress row
            return None
        return {
            "status": row[offset], "is_favorite": bool(row[offset + 1]), "current_chapter": row[offset + 2],
            "current_sentence_index": row[offset + 3], "completion_percentage": float(row[offset + 4] or 0),
            "last_read_at": row[offset + 5], "voice": row[offset + 6],
        }

    def _where(self, query: str, category_id: int | None, source: str, params: dict[str, Any], *, shelf: bool) -> str:
        clauses = ["(b.owner_id = :me OR (b.is_public = 1 AND p.user_id IS NOT NULL))" if shelf else "b.is_public = 1"]
        params["me"] = self.user_id
        for index, token in enumerate(search_tokens(query)):
            clauses.append(f"b.search_text LIKE :tok{index}")
            params[f"tok{index}"] = f"%{token.replace('%', '').replace('_', '')}%"
        if category_id is not None:
            clauses.append("b.category_id = :cat")
            params["cat"] = category_id
        if shelf and source == "system":
            clauses.append("b.is_public = 1")
        elif shelf and source == "mine":
            clauses.append("b.owner_id = :me")
        return " AND ".join(clauses)

    def list_shelf(self, *, query: str = "", category_id: int | None = None, source: str = "all",
                   status: str | None = None, sort: str = "recent", limit: int = 200, offset: int = 0) -> list[ShelfEntry]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        where = self._where(query, category_id, source, params, shelf=True)
        if status == "favorite":
            where += " AND p.is_favorite = 1"
        elif status in STATUSES:
            where += " AND COALESCE(p.status, 'unread') = :status"
            params["status"] = status
        order = {
            "title": "b.title ASC, b.id DESC",
            "newest": "b.id DESC",
            "progress": "COALESCE(p.completion_percentage, 0) DESC, b.id DESC",
        }.get(sort, "(p.last_read_at IS NULL), p.last_read_at DESC, b.id DESC")
        return self._run(where, order, params, shelf=True)

    def list_public(self, *, query: str = "", category_id: int | None = None, sort: str = "newest",
                    limit: int = 200, offset: int = 0) -> list[ShelfEntry]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        where = self._where(query, category_id, "all", params, shelf=False)
        order = "b.title ASC, b.id DESC" if sort == "title" else "b.id DESC"
        return self._run(where, order, params, shelf=False)

    def _run(self, where: str, order: str, params: dict[str, Any], *, shelf: bool) -> list[ShelfEntry]:
        columns = ", ".join(f"b.{c}" for c in SqlBookRepository._BOOK_COLS.split(", "))
        sql = (
            f"SELECT {columns}, {self._PROGRESS} FROM books b "  # noqa: S608
            "LEFT JOIN user_book_progress p ON p.book_id = b.id AND p.user_id = :me "
            f"WHERE {where} ORDER BY {order} LIMIT :limit OFFSET :offset"
        )
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        entries = []
        for row in rows:
            book = SqlBookRepository._book(row)
            progress = self._progress(row, 15)
            entries.append(ShelfEntry(book, progress, on_shelf=shelf or book.owner_id == self.user_id or progress is not None))
        return entries

    def counts(self, *, query: str = "", category_id: int | None = None, source: str = "all") -> dict[str, int]:
        """How many shelf books are in each tab, for the same search/category/source filters."""
        params: dict[str, Any] = {}
        where = self._where(query, category_id, source, params, shelf=True)
        sql = (
            "SELECT COALESCE(p.status, 'unread'), COALESCE(p.is_favorite, 0), COUNT(*) FROM books b "  # noqa: S608
            "LEFT JOIN user_book_progress p ON p.book_id = b.id AND p.user_id = :me "
            f"WHERE {where} GROUP BY COALESCE(p.status, 'unread'), COALESCE(p.is_favorite, 0)"
        )
        result = {"unread": 0, "reading": 0, "completed": 0, "favorite": 0}
        with self.engine.connect() as conn:
            for status, favorite, count in conn.execute(text(sql), params).fetchall():
                result[status if status in result else "unread"] += int(count)
                if favorite:
                    result["favorite"] += int(count)
        return result

    # -- changes (each makes sure the user has a progress row, which is what "on the shelf" means) ----

    def _ensure(self, conn: Any, book_id: int) -> None:
        exists = conn.execute(
            text("SELECT 1 FROM user_book_progress WHERE user_id = :u AND book_id = :b"), {"u": self.user_id, "b": book_id}
        ).fetchone()
        if exists is None:
            conn.execute(
                text("INSERT INTO user_book_progress (user_id, book_id, status, last_read_at) VALUES (:u, :b, 'unread', :now)"),
                {"u": self.user_id, "b": book_id, "now": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")},
            )

    def add(self, book_id: int) -> None:
        with self.engine.begin() as conn:
            self._ensure(conn, book_id)

    def remove(self, book_id: int) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM user_book_progress WHERE user_id = :u AND book_id = :b"), {"u": self.user_id, "b": book_id})

    def set_favorite(self, book_id: int, favorite: bool) -> None:
        with self.engine.begin() as conn:
            self._ensure(conn, book_id)
            conn.execute(
                text("UPDATE user_book_progress SET is_favorite = :f WHERE user_id = :u AND book_id = :b"),
                {"f": 1 if favorite else 0, "u": self.user_id, "b": book_id},
            )

    def set_status(self, book_id: int, status: str, total_sentences: int, last_chapter: int) -> None:
        """"Đã nghe xong" (completed: goes to the last sentence) or "nghe lại từ đầu" (unread: back to the start)."""
        if status not in ("completed", "unread"):
            raise ValueError("status must be 'completed' or 'unread'")
        finished = status == "completed"
        with self.engine.begin() as conn:
            self._ensure(conn, book_id)
            conn.execute(
                text("""
                    UPDATE user_book_progress SET status = :s, current_chapter = :c, current_sentence_index = :i,
                        completion_percentage = :p, last_read_at = :now WHERE user_id = :u AND book_id = :b
                """),
                {"s": status, "c": last_chapter if finished else 1, "i": max(total_sentences - 1, 0) if finished else 0,
                 "p": 100.0 if finished else 0.0, "u": self.user_id, "b": book_id,
                 "now": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")},
            )
