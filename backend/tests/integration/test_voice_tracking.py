"""Voice stored per session/bookmark, per-voice stats, column upgrades and export cancellation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, inspect, text

from src.core.audio.export import cancel_job, create_job, run_export
from src.core.models.book import BookSentence
from src.core.storage.migrations import run_migrations, upgrade_columns
from tests.auth_helpers import TESTER_ID
from tests.integration.test_api_extended import add_book, client, provider  # noqa: F401


def _session(book_id: int, voice: str | None, seconds: int = 60) -> dict:
    now = datetime.now(UTC)
    body = {
        "book_id": book_id, "duration_seconds": seconds, "sentences_read": 3, "words_read": 30,
        "start_time": (now - timedelta(seconds=seconds)).isoformat(), "end_time": now.isoformat(),
    }
    if voice is not None:
        body["voice"] = voice
    return body


def test_session_voice_is_stored_and_aggregated(client: TestClient, test_engine: Engine) -> None:  # noqa: F811
    book_id = add_book(test_engine)
    created = client.post("/api/sessions", json=_session(book_id, "mock-vi-female", 120))
    assert created.status_code == 201 and created.json()["voice"] == "mock-vi-female"
    client.post("/api/sessions", json=_session(book_id, "mock-vi-female", 60))
    client.post("/api/sessions", json=_session(book_id, "mock-vi-male", 30))
    client.post("/api/sessions", json=_session(book_id, None, 30))  # recorded by an older client

    stats = client.get("/api/analytics/voices?days=7").json()
    by_voice = {row["voice"]: row for row in stats}
    assert by_voice["mock-vi-female"]["minutes"] == 3.0 and by_voice["mock-vi-female"]["sessions"] == 2
    assert by_voice["mock-vi-male"]["minutes"] == 0.5
    assert by_voice[""]["display_name"] == "Không rõ"
    assert [row["voice"] for row in stats][0] == "mock-vi-female"  # biggest share first


def test_bookmark_remembers_last_voice(client: TestClient, test_engine: Engine) -> None:  # noqa: F811
    book_id = add_book(test_engine)
    assert client.get(f"/api/bookmarks/{book_id}").json()["voice"] is None
    client.post("/api/bookmarks", json={"book_id": book_id, "current_sentence_index": 1, "voice": "mock-vi-male"})
    assert client.get(f"/api/bookmarks/{book_id}").json()["voice"] == "mock-vi-male"
    # a later save without a voice (older client) must not erase it
    client.post("/api/bookmarks", json={"book_id": book_id, "current_sentence_index": 2})
    saved = client.get(f"/api/bookmarks/{book_id}").json()
    assert saved["voice"] == "mock-vi-male" and saved["current_sentence_index"] == 2


def test_upgrade_adds_missing_columns_to_an_old_database() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:  # the schema of the first release: no voice columns
        conn.execute(text("CREATE TABLE reading_sessions (id INTEGER PRIMARY KEY, book_id INT)"))
        conn.execute(text("CREATE TABLE bookmarks (id INTEGER PRIMARY KEY, book_id INT)"))
        conn.execute(text("INSERT INTO reading_sessions (book_id) VALUES (1)"))
    assert sorted(upgrade_columns(engine)) == ["bookmarks.voice", "reading_sessions.user_id", "reading_sessions.voice"]
    assert upgrade_columns(engine) == []  # idempotent
    names = {c["name"] for c in inspect(engine).get_columns("reading_sessions")}
    assert "voice" in names
    with engine.connect() as conn:  # existing rows survive
        assert conn.execute(text("SELECT COUNT(*) FROM reading_sessions")).scalar() == 1


def test_run_migrations_is_repeatable(test_engine: Engine) -> None:
    run_migrations(test_engine)
    run_migrations(test_engine)
    assert "voice" in {c["name"] for c in inspect(test_engine).get_columns("bookmarks")}


def test_cancelled_export_stops_and_produces_no_file(test_engine: Engine, client: TestClient, tmp_path) -> None:  # noqa: F811
    sentences = [
        BookSentence(id=None, book_id=1, chapter_index=1, sentence_index=i, text_content=f"Câu {i}.",
                     word_count=2, content_hash=f"{i:064d}")
        for i in range(3)
    ]
    job = create_job(1, total=3)
    cancel_job(job)
    run_export(test_engine, job, sentences, "mock-vi-female", 1.0, None, "x")
    assert job.status == "cancelled" and job.done == 0 and job.file_path is None


def test_cancel_endpoint(client: TestClient) -> None:  # noqa: F811
    job = create_job(1, total=5, user_id=TESTER_ID)
    resp = client.delete(f"/api/exports/{job.job_id}")
    assert resp.status_code == 200 and job.cancel_requested.is_set()
    assert client.delete("/api/exports/does-not-exist").status_code == 404
    job.status = "done"
    cancel_job(job)  # finished jobs are not affected
    assert job.status == "done"
