"""Unit tests for Book API routes and sentence catalog retrieval."""

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


def test_get_book_sentences_not_found(app_client: TestClient) -> None:
    """Test fetching sentences for missing book returns 404."""
    resp = app_client.get("/api/books/999/sentences")
    assert resp.status_code == 404


def test_get_book_sentences_success(app_client: TestClient, test_engine: Engine) -> None:
    """Test fetching sentence list for an ingested book."""
    book_repo = SqlBookRepository(test_engine)
    book = Book(owner_id=TESTER_ID,
        id=None,
        title="Sentence Book",
        author="Test Author",
        source_path="test2.txt",
        content_hash="c" * 64,
        total_chapters=1,
        total_sentences=2,
        total_words=10,
    )
    sentences = [
        BookSentence(
            id=None,
            book_id=0,
            chapter_index=1,
            sentence_index=0,
            text_content="First sentence text.",
            word_count=3,
            content_hash="d" * 64,
        ),
        BookSentence(
            id=None,
            book_id=0,
            chapter_index=1,
            sentence_index=1,
            text_content="Second sentence text.",
            word_count=3,
            content_hash="e" * 64,
        ),
    ]
    book_id = book_repo.save_book(book, sentences)

    resp = app_client.get(f"/api/books/{book_id}/sentences")
    assert resp.status_code == 200
    data = resp.json()
    assert data["book_id"] == book_id
    assert data["total_sentences"] == 2
    assert len(data["sentences"]) == 2
    assert data["sentences"][0]["sentence_index"] == 0
    assert data["sentences"][0]["text_content"] == "First sentence text."
    assert data["sentences"][1]["sentence_index"] == 1
