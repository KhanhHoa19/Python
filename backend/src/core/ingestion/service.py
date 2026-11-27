"""Service orchestrating file ingestion, document parsing, content hashing, and catalog persistence."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from src.core.ingestion.covers import (
    generate_default_cover,
    hue_for,
    normalize_uploaded_cover,
    render_pdf_cover,
    save_cover,
)
from src.core.ingestion.parser import (
    PREFACE_TITLE,
    WHOLE_DOCUMENT_TITLE,
    split_into_chapters_and_sentences,
)
from src.core.ingestion.reader import DocumentReader
from src.core.models.book import Book, BookSentence, Chapter
from src.core.storage.db import get_db_engine
from src.core.storage.library import hue_of_color
from src.core.storage.repositories import SqlBookRepository, SqlCategoryRepository

logger = logging.getLogger(__name__)


class IngestionService:
    """Coordinates reading, parsing, and persisting books in the library."""

    def __init__(self, book_repo: SqlBookRepository | None = None):
        self.book_repo = book_repo or SqlBookRepository(get_db_engine())

    def ingest_file(
        self,
        file_path: str | Path,
        title: str | None = None,
        author: str = "Unknown",
        owner_id: int | None = None,
        is_public: bool = False,
        category_id: int | None = None,
        cover_image: bytes | None = None,
    ) -> Book:
        """
        Load and parse a document file, cataloging it into the database.
        If an identical book is already ingested (by SHA-256 content hash),
        the existing record is returned without duplication.
        """
        content, filename, content_hash, headings = DocumentReader.load_with_headings(file_path)

        # Check for existing duplicate
        existing = self.book_repo.get_by_hash(content_hash, owner_id)
        if existing:
            logger.info(f"Book with hash {content_hash} already cataloged (ID: {existing.id}). Returning existing record.")
            return existing

        resolved_title = title.strip() if title and title.strip() else Path(filename).stem.replace("_", " ").title()

        # Parse into chapters and sentences (applying 35-word clause threshold)
        parsed_chapters = split_into_chapters_and_sentences(content, max_clause_words=35, heading_hints=headings)
        if len(parsed_chapters) == 1 and parsed_chapters[0]["title"] == PREFACE_TITLE:
            parsed_chapters[0]["title"] = WHOLE_DOCUMENT_TITLE  # no heading anywhere: one chapter, the whole text
        chapters: list[Chapter] = []

        total_words = 0
        total_sentences = 0
        sentences: list[BookSentence] = []
        global_sentence_idx = 0

        for chap_idx, chap in enumerate(parsed_chapters, start=1):
            first_sentence = global_sentence_idx
            chapter_words = 0
            for s_text in chap["sentences"]:
                words = len(s_text.split())
                total_words += words
                chapter_words += words
                s_hash = hashlib.sha256(s_text.encode("utf-8")).hexdigest()

                sentence_obj = BookSentence(
                    book_id=0,  # Updated after book insertion
                    chapter_index=chap_idx,
                    sentence_index=global_sentence_idx,
                    text_content=s_text,
                    word_count=words,
                    content_hash=s_hash,
                )
                sentences.append(sentence_obj)
                global_sentence_idx += 1
            chapters.append(Chapter(chap_idx, chap["title"], first_sentence, global_sentence_idx - 1, chapter_words))

        total_sentences = len(sentences)

        categories = SqlCategoryRepository(self.book_repo.engine)
        category = categories.get(category_id) if category_id is not None else None
        if category is None:  # nobody (or nobody valid) chose: "Khác"
            category = categories.get(categories.default_id() or -1)
        cover_name = self._make_cover(file_path, resolved_title, author, category, cover_image)

        book = Book(
            title=resolved_title,
            author=author,
            source_path=str(Path(file_path).resolve()),
            content_hash=content_hash,
            total_chapters=len(parsed_chapters),
            total_sentences=total_sentences,
            total_words=total_words,
            owner_id=owner_id,
            is_public=is_public,
            category_id=category["id"] if category else None,
            cover_path=cover_name,
        )

        book_id = self.book_repo.save_book(book, sentences, chapters)
        book.id = book_id
        logger.info(f"Successfully cataloged '{book.title}' with {total_sentences} sentences and {total_words} words (ID: {book_id}).")
        return book

    @staticmethod
    def _make_cover(
        file_path: str | Path, title: str, author: str, category: dict | None, uploaded: bytes | None
    ) -> str:
        """Cover file name: the user's own image, else page 1 of a PDF, else a generated cover tinted by the category.
        Never raises for a bad PDF; a bad uploaded image is the caller's error (CoverError, a ValueError)."""
        if uploaded:
            return save_cover(normalize_uploaded_cover(uploaded))
        jpeg = render_pdf_cover(file_path) if Path(file_path).suffix.lower() == ".pdf" else None
        if jpeg is None:
            hue = hue_of_color(category["color"]) if category else hue_for(title)
            jpeg = generate_default_cover(title, author, hue)
        return save_cover(jpeg)
