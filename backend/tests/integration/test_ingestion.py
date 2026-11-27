"""Integration tests for document ingestion and database cataloging."""

from __future__ import annotations

import tempfile
from pathlib import Path

from sqlalchemy import Engine

from src.core.ingestion.service import IngestionService
from src.core.storage.repositories import SqlBookRepository


def test_ingest_plain_text_file(test_engine: Engine):
    sample_content = (
        "Chapter 1: The Beginning\n\n"
        "It was the best of times, it was the worst of times. "
        "We had everything before us, we had nothing before us.\n\n"
        "Chapter 2: The Journey\n\n"
        "The travelers prepared their horses at dawn. "
        "The road ahead was fraught with uncertainty."
    )
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(sample_content)
        temp_path = f.name

    try:
        book_repo = SqlBookRepository(test_engine)
        service = IngestionService(book_repo=book_repo)

        book = service.ingest_file(temp_path, title="A Tale of Two Chapters", author="Charles Dickens", owner_id=2)
        assert book.id is not None
        assert book.title == "A Tale of Two Chapters"
        assert book.author == "Charles Dickens"
        assert book.total_chapters == 2
        assert book.total_sentences == 4
        assert book.total_words > 0

        # Verify database records
        db_book = book_repo.get_by_id(book.id)
        assert db_book is not None
        assert db_book.content_hash == book.content_hash

        sentences = book_repo.get_sentences(book.id, start_idx=0, limit=10)
        assert len(sentences) == 4
        assert sentences[0].sentence_index == 0
        assert sentences[3].sentence_index == 3

        assert db_book.owner_id == 2 and not db_book.is_public

        # Duplicate ingestion check: the same owner re-ingesting identical content gets the existing book ...
        dup_book = service.ingest_file(temp_path, title="Duplicate Import", owner_id=2)
        assert dup_book.id == book.id
        # ... while another person importing the same file gets a book of their own.
        other = service.ingest_file(temp_path, title="Same file, other reader", owner_id=1)
        assert other.id != book.id and other.owner_id == 1
    finally:
        Path(temp_path).unlink(missing_ok=True)
