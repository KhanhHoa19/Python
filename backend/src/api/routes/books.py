"""Books API router: catalog listing, rename, sentence retrieval, and file ingestion."""

from __future__ import annotations

import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import JSONResponse

from src.api.deps import current_user, editable_book, visible_book
from src.api.schemas.book_schemas import (
    BookChaptersResponse,
    BookDetailResponse,
    BookSentenceResponse,
    BookSentencesListResponse,
    BookSummaryResponse,
    BookUpdateRequest,
    BookUploadSuccessResponse,
    CategoryResponse,
    ChapterResponse,
    FavoriteRequest,
    ProgressResponse,
    ShelfCountsResponse,
    StatusRequest,
)
from src.core.audio.quotes import delete_quote_audio
from src.core.auth.users import User
from src.core.ingestion.covers import (
    MAX_COVER_UPLOAD_BYTES,
    CoverError,
    cover_url,
    delete_cover,
    normalize_uploaded_cover,
    save_cover,
)
from src.core.ingestion.service import IngestionService
from src.core.player.cache_manager import AudioCacheManager
from src.core.storage.db import get_db_engine
from src.core.storage.repositories import (
    ShelfEntry,
    SqlBookRepository,
    SqlCategoryRepository,
    SqlNoteRepository,
    SqlShelfRepository,
)

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


def _progress(progress: dict[str, Any] | None) -> ProgressResponse | None:
    if progress is None:
        return None
    last = progress["last_read_at"]
    return ProgressResponse(**{**progress, "last_read_at": _format_dt(last)})


def _summary(entry: ShelfEntry, user: User, categories: dict[int, dict[str, Any]]) -> BookSummaryResponse:
    b = entry.book
    category = categories.get(b.category_id) if b.category_id is not None else None
    return BookSummaryResponse(
        id=b.id or 0, title=b.title, author=b.author, total_chapters=b.total_chapters,
        total_sentences=b.total_sentences, total_words=b.total_words, created_at=_format_dt(b.created_at),
        is_public=b.is_public, is_mine=b.owner_id == user.id, on_shelf=entry.on_shelf,
        category=CategoryResponse(**category) if category else None,
        cover_url=cover_url(b.cover_path), progress=_progress(entry.progress),
    )


def _categories(engine: Any) -> dict[int, dict[str, Any]]:
    return {c["id"]: c for c in SqlCategoryRepository(engine).list_all()}


def _category_id(engine: Any, value: str | int | None) -> int | None:
    """A category id or slug from a query string; unknown values are a 400, not an empty list."""
    if value in (None, ""):
        return None
    for category in SqlCategoryRepository(engine).list_all():
        if str(value) in (str(category["id"]), category["slug"]):
            return int(category["id"])
    raise HTTPException(400, f"Unknown category '{value}'")


@router.get("", response_model=list[BookSummaryResponse])
def list_books(
    q: str = "", category: str | None = None, source: Literal["all", "system", "mine"] = "all",
    status: Literal["unread", "reading", "completed", "favorite"] | None = None,
    sort: Literal["recent", "title", "newest", "progress"] = "recent",
    limit: int = 200, offset: int = 0, user: User = Depends(current_user),
) -> list[BookSummaryResponse]:
    """The caller's shelf: own books plus public books they added, with their progress. Filters combine (AND)."""
    engine = get_db_engine()
    entries = SqlShelfRepository(engine, user.id).list_shelf(
        query=q, category_id=_category_id(engine, category), source=source, status=status, sort=sort,
        limit=min(max(limit, 1), 500), offset=max(offset, 0),
    )
    categories = _categories(engine)
    return [_summary(e, user, categories) for e in entries]


@router.get("/counts", response_model=ShelfCountsResponse)
def shelf_counts(
    q: str = "", category: str | None = None, source: Literal["all", "system", "mine"] = "all",
    user: User = Depends(current_user),
) -> ShelfCountsResponse:
    """Books per shelf tab (reading / unread / completed / favorite) for the same search, category and source."""
    engine = get_db_engine()
    return ShelfCountsResponse(**SqlShelfRepository(engine, user.id).counts(
        query=q, category_id=_category_id(engine, category), source=source))


@router.get("/explore", response_model=list[BookSummaryResponse])
def explore_books(
    q: str = "", category: str | None = None, sort: Literal["newest", "title"] = "newest",
    limit: int = 200, offset: int = 0, user: User = Depends(current_user),
) -> list[BookSummaryResponse]:
    """The public catalogue (system books). `on_shelf` tells whether the caller already added a book."""
    engine = get_db_engine()
    entries = SqlShelfRepository(engine, user.id).list_public(
        query=q, category_id=_category_id(engine, category), sort=sort,
        limit=min(max(limit, 1), 500), offset=max(offset, 0),
    )
    categories = _categories(engine)
    return [_summary(e, user, categories) for e in entries]


def _detail(book: Any, user: User) -> BookDetailResponse:
    mine = book.owner_id == user.id
    category = _categories(get_db_engine()).get(book.category_id) if book.category_id is not None else None
    return BookDetailResponse(
        id=book.id or 0,
        title=book.title,
        author=book.author,
        source_path=book.source_path if mine else "",  # a server path is nobody else's business
        content_hash=book.content_hash,
        total_chapters=book.total_chapters,
        total_sentences=book.total_sentences,
        total_words=book.total_words,
        created_at=_format_dt(book.created_at),
        is_public=book.is_public,
        is_mine=mine,
        category=CategoryResponse(**category) if category else None,
        cover_url=cover_url(book.cover_path),
    )


@router.get("/{book_id}", response_model=BookDetailResponse)
def get_book_detail(book_id: int, user: User = Depends(current_user)) -> BookDetailResponse:
    """Retrieve detailed metadata for a book."""
    return _detail(visible_book(get_db_engine(), book_id, user), user)


@router.patch("/{book_id}", response_model=BookDetailResponse)
def update_book(book_id: int, req: BookUpdateRequest, user: User = Depends(current_user)) -> BookDetailResponse:
    """Change a book's title (trimmed, 1-255 characters) and/or its category. Only the sent fields change."""
    engine = get_db_engine()
    if req.title is None and req.author is None and "category_id" not in req.model_fields_set:
        raise HTTPException(400, "Send a title, an author and/or a category_id.")
    editable_book(engine, book_id, user)
    repo = SqlBookRepository(engine)
    if req.title is not None or req.author is not None:
        repo.update_text(book_id, req.title, req.author)
    if "category_id" in req.model_fields_set:
        if req.category_id is not None and SqlCategoryRepository(engine).get(req.category_id) is None:
            raise HTTPException(400, f"Unknown category {req.category_id}")
        repo.set_category(book_id, req.category_id)
    book = repo.get_book(book_id)
    assert book is not None
    return _detail(book, user)


@router.put("/{book_id}/cover", response_model=BookDetailResponse)
def replace_cover(book_id: int, file: UploadFile = File(...), user: User = Depends(current_user)) -> BookDetailResponse:
    """Use an uploaded JPEG/PNG (<= 2 MB) as the book's cover."""
    engine = get_db_engine()
    book = editable_book(engine, book_id, user)
    data = file.file.read(MAX_COVER_UPLOAD_BYTES + 1)
    try:
        name = save_cover(normalize_uploaded_cover(data))
    except CoverError as exc:
        raise HTTPException(400, str(exc)) from exc
    repo = SqlBookRepository(engine)
    repo.set_cover(book_id, name)
    delete_cover(book.cover_path)
    updated = repo.get_book(book_id)
    assert updated is not None
    return _detail(updated, user)


@router.post("/{book_id}/shelf", status_code=204)
def add_to_shelf(book_id: int, user: User = Depends(current_user)) -> Response:
    """Put a public book on the caller's shelf (own books are always there)."""
    engine = get_db_engine()
    visible_book(engine, book_id, user)
    SqlShelfRepository(engine, user.id).add(book_id)
    return Response(status_code=204)


@router.delete("/{book_id}/shelf", status_code=204)
def remove_from_shelf(book_id: int, user: User = Depends(current_user)) -> Response:
    """Take a public book off the caller's shelf; their progress in it is forgotten. Own books: delete them instead."""
    engine = get_db_engine()
    book = visible_book(engine, book_id, user)
    if book.owner_id == user.id:
        raise HTTPException(400, "This is your own book: delete it instead.")
    SqlShelfRepository(engine, user.id).remove(book_id)
    return Response(status_code=204)


@router.put("/{book_id}/favorite", status_code=204)
def set_favorite(book_id: int, req: FavoriteRequest, user: User = Depends(current_user)) -> Response:
    engine = get_db_engine()
    visible_book(engine, book_id, user)
    SqlShelfRepository(engine, user.id).set_favorite(book_id, req.is_favorite)
    return Response(status_code=204)


@router.put("/{book_id}/status", status_code=204)
def set_status(book_id: int, req: StatusRequest, user: User = Depends(current_user)) -> Response:
    """`completed` = "Đánh dấu đã nghe xong"; `unread` = start over (position back to the first sentence)."""
    engine = get_db_engine()
    book = visible_book(engine, book_id, user)
    chapters = SqlBookRepository(engine).get_chapters(book_id)
    SqlShelfRepository(engine, user.id).set_status(
        book_id, req.status, book.total_sentences, chapters[-1].chapter_index if chapters else 1)
    return Response(status_code=204)


@router.delete("/{book_id}", status_code=204)
def delete_book(book_id: int, user: User = Depends(current_user)) -> Response:
    """Delete a book with its sentences, bookmark, sessions, notes, cover and cached audio."""
    engine = get_db_engine()
    book = editable_book(engine, book_id, user)
    quote_audio = SqlNoteRepository.audio_paths_for_book(engine, book_id)  # read before the rows disappear
    SqlBookRepository(engine).delete_book(book_id)
    delete_cover(book.cover_path)
    for relative in quote_audio:
        delete_quote_audio(relative)
    AudioCacheManager().clear_book_cache(book_id)
    return Response(status_code=204)


@router.get("/{book_id}/sentences", response_model=BookSentencesListResponse)
def get_book_sentences(book_id: int, user: User = Depends(current_user)) -> BookSentencesListResponse:
    """Fetch all indexed sentences for a book for text synchronization."""
    engine = get_db_engine()
    visible_book(engine, book_id, user)
    book_repo = SqlBookRepository(engine)

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


@router.get("/{book_id}/chapters", response_model=BookChaptersResponse)
def get_book_chapters(book_id: int, user: User = Depends(current_user)) -> BookChaptersResponse:
    """Table of contents: every chapter with its title and the sentence range it covers."""
    engine = get_db_engine()
    visible_book(engine, book_id, user)
    book_repo = SqlBookRepository(engine)
    return BookChaptersResponse(
        book_id=book_id,
        chapters=[
            ChapterResponse(
                chapter_index=c.chapter_index, title=c.title, start_sentence_index=c.start_sentence_index,
                end_sentence_index=c.end_sentence_index, sentence_count=c.sentence_count, word_count=c.word_count,
            )
            for c in book_repo.get_chapters(book_id)
        ],
    )


@router.post("/ingest", status_code=201, response_model=BookUploadSuccessResponse)
def ingest_book_file(
    file: UploadFile | None = File(None),
    title: str | None = Form(None),
    author: str | None = Form(None),
    is_public: bool = Form(False),
    category_id: int | None = Form(None),
    cover: UploadFile | None = File(None),
    user: User = Depends(current_user),
) -> Any:
    """Upload and catalog a book. It is private to the uploader; only an admin can publish it for everyone."""
    if is_public and not user.is_admin:
        raise HTTPException(403, "Only an administrator can upload a public book.")
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
        book = service.ingest_file(
            file_path=temp_path, title=title, author=author, owner_id=user.id, is_public=is_public,
            category_id=category_id, cover_image=cover.file.read(MAX_COVER_UPLOAD_BYTES + 1) if cover else None,
        )
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
