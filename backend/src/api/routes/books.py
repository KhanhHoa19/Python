"""Books API router: catalog listing, sentence retrieval, and file ingestion."""

from __future__ import annotations

import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import JSONResponse

from src.api.schemas.book_schemas import (
    BookDetailResponse,
    BookSentenceResponse,
    BookSentencesListResponse,
    BookSummaryResponse,
    BookUploadSuccessResponse,
)
from src.core.ingestion.service import IngestionService
from src.core.player.cache_manager import AudioCacheManager
from src.core.storage.db import get_db_engine
from src.core.storage.repositories import SqlBookRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["books"])

_ALLOWED_UPLOADS = {".txt", ".md", ".pdf", ".docx"}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _format_dt(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val)


@router.get("", response_model=list[BookSummaryResponse])
def list_books(limit: int = 50, offset: int = 0) -> list[BookSummaryResponse]:
    """List all cataloged books with pagination."""
    book_repo = SqlBookRepository(get_db_engine())
    return [
        BookSummaryResponse(
            id=b.id or 0,
            title=b.title,
            author=b.author,
            total_chapters=b.total_chapters,
            total_sentences=b.total_sentences,
            total_words=b.total_words,
            created_at=_format_dt(b.created_at),
        )
        for b in book_repo.list_books(limit=limit, offset=offset)
    ]


@router.get("/{book_id}", response_model=BookDetailResponse)
def get_book_detail(book_id: int) -> BookDetailResponse:
    """Retrieve detailed metadata for a book."""
    book = SqlBookRepository(get_db_engine()).get_book(book_id)
    if not book:
        raise HTTPException(404, f"Book {book_id} not found")
    return BookDetailResponse(
        id=book.id or 0,
        title=book.title,
        author=book.author,
        source_path=book.source_path,
        content_hash=book.content_hash,
        total_chapters=book.total_chapters,
        total_sentences=book.total_sentences,
        total_words=book.total_words,
        created_at=_format_dt(book.created_at),
    )


@router.delete("/{book_id}", status_code=204)
def delete_book(book_id: int) -> Response:
    """Delete a book with its sentences, bookmark, sessions, notes and cached audio."""
    if not SqlBookRepository(get_db_engine()).delete_book(book_id):
        raise HTTPException(404, f"Book {book_id} not found")
    AudioCacheManager().clear_book_cache(book_id)
    return Response(status_code=204)


@router.get("/{book_id}/sentences", response_model=BookSentencesListResponse)
def get_book_sentences(book_id: int) -> BookSentencesListResponse:
    """Fetch all indexed sentences for a book for text synchronization."""
    book_repo = SqlBookRepository(get_db_engine())
    if not book_repo.get_book(book_id):
        raise HTTPException(404, f"Book {book_id} not found")

    sentences = book_repo.get_book_sentences(book_id)
    return BookSentencesListResponse(
        book_id=book_id,
        total_sentences=len(sentences),
        sentences=[
            BookSentenceResponse(
                sentence_index=s.sentence_index,
                chapter_index=s.chapter_index,
                text_content=s.text_content,
                word_count=s.word_count,
            )
            for s in sentences
        ],
    )


@router.post("/ingest", status_code=201, response_model=BookUploadSuccessResponse)
def ingest_book_file(
    file: UploadFile | None = File(None),
    title: str | None = Form(None),
    author: str | None = Form(None),
) -> Any:
    """Upload and catalog a text or markdown book file."""
    if file is None:
        raise HTTPException(400, "No file uploaded")
    if not file.filename:
        raise HTTPException(400, "Empty filename")

    filename = file.filename.lower()
    suffix = Path(filename).suffix
    if suffix not in _ALLOWED_UPLOADS:
        raise HTTPException(
            400, "Unsupported file format. Only .txt, .md, .pdf and .docx files are supported."
        )

    title = title or Path(file.filename).stem.replace("_", " ").title()
    author = author or "Unknown"

    content = file.file.read(_MAX_UPLOAD_BYTES + 1)
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(400, "File exceeds 10 MB.")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
        temp_file.write(content)
        temp_path = temp_file.name

    try:
        service = IngestionService(book_repo=SqlBookRepository(get_db_engine()))
        book = service.ingest_file(file_path=temp_path, title=title, author=author)
        return BookUploadSuccessResponse(
            book_id=book.id or 0,
            title=book.title,
            total_chapters=book.total_chapters,
            total_sentences=book.total_sentences,
            total_words=book.total_words,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.error(f"Book ingestion failed: {exc}")
        return JSONResponse({"error": f"Failed to ingest book: {exc}"}, status_code=500)
    finally:
        Path(temp_path).unlink(missing_ok=True)
