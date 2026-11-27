"""Unit tests for Bookmark and Session API endpoints."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from src.api.app import create_app
from src.core.models.book import Book, BookSentence
from src.core.storage.repositories import SqlBookRepository
from tests.auth_helpers import TESTER_ID, sign_in, tester, use_engine


@pytest.fixture
def app_client(test_engine: Engine) -> Generator[TestClient, None, None]:
    """Create FastAPI test client with in-memory database engine."""
    with use_engine(test_engine):
        app = create_app()
        with TestClient(app) as client:
            yield sign_in(client, test_engine, tester(test_engine))


def test_get_bookmark_defaults_for_new_book(app_client: TestClient, test_engine: Engine) -> None:
    """A book the user never opened starts at sentence 0; a book that does not exist is a 404."""
    assert app_client.get("/api/bookmarks/999").status_code == 404
    book_id = SqlBookRepository(test_engine).save_book(
        Book(owner_id=TESTER_ID, title="New", author="A", source_path="n.txt", content_hash="d" * 64,
             total_chapters=1, total_sentences=1, total_words=1), [])
    resp = app_client.get(f"/api/bookmarks/{book_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["book_id"] == book_id
    assert data["current_sentence_index"] == 0
    assert data["completion_percentage"] == 0.0


def test_update_and_get_bookmark(app_client: TestClient, test_engine: Engine) -> None:
    """Test updating bookmark position and verifying retrieval."""
    book_repo = SqlBookRepository(test_engine)
    book = Book(owner_id=TESTER_ID,
        id=None,
        title="Bookmark Test Book",
        author="Author",
        source_path="test.txt",
        content_hash="x" * 64,
        total_chapters=1,
        total_sentences=10,
        total_words=100,
    )
    book_id = book_repo.save_book(book, [])

    # Update bookmark to sentence 4
    update_payload = {
        "book_id": book_id,
        "current_chapter": 1,
        "current_sentence_index": 4,
        "completion_percentage": 40.0,
    }
    post_resp = app_client.post("/api/bookmarks", json=update_payload)
    assert post_resp.status_code == 200
    assert post_resp.json()["status"] == "updated"

    # Get updated bookmark
    get_resp = app_client.get(f"/api/bookmarks/{book_id}")
    assert get_resp.status_code == 200
    bm = get_resp.json()
    assert bm["book_id"] == book_id
    assert bm["current_sentence_index"] == 4
    assert bm["completion_percentage"] == 40.0


def test_record_reading_session(app_client: TestClient, test_engine: Engine) -> None:
    """Test posting a reading session row (the book must exist: MySQL enforces the foreign key)."""
    book_id = SqlBookRepository(test_engine).save_book(
        Book(owner_id=TESTER_ID, id=None, title="Session Book", author="A", source_path="s.txt", content_hash="e" * 64,
             total_chapters=1, total_sentences=1, total_words=3),
        [BookSentence(id=None, book_id=0, chapter_index=1, sentence_index=0, text_content="Một câu.",
                      word_count=2, content_hash="f" * 64)],
    )
    payload = {
        "book_id": book_id,
        "duration_seconds": 120,
        "sentences_read": 8,
        "words_read": 110,
        "start_time": "2026-11-21T12:00:00Z",
        "end_time": "2026-11-21T12:02:00Z",
    }
    resp = app_client.post("/api/sessions", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["book_id"] == book_id
    assert body["duration_seconds"] == 120
    assert body["sentences_read"] == 8
    assert body["words_read"] == 110
