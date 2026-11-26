"""Player API router: audio streaming, bookmarks, and reading sessions."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.api.schemas.player_schemas import (
    BookmarkResponse,
    BookmarkUpdateRequest,
    ReadingSessionCreateRequest,
    ReadingSessionResponse,
)
from src.core.app_settings import load_app_settings
from src.core.models.session import ReadingSession
from src.core.player.audio_service import QuotaExceededError, get_or_create_audio
from src.core.storage.db import get_db_engine
from src.core.storage.repositories import (
    SqlBookmarkRepository,
    SqlBookRepository,
    SqlSessionRepository,
    SqlSettingsRepository,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["player"])

_AUDIO_HEADERS = {"Cache-Control": "public, max-age=86400"}


def _media_type(path: Path) -> str:
    return {"mp3": "audio/mpeg", "wav": "audio/wav", "ogg": "audio/ogg"}.get(
        path.suffix.lstrip(".").lower(), "application/octet-stream"
    )


@router.get("/audio/{book_id}/{sentence_index}")
def stream_sentence_audio(
    book_id: int, sentence_index: int, speed: float = 1.0, voice: str | None = None
) -> FileResponse:
    """Stream synthesized MP3 audio for an indexed sentence."""
    if speed < 0.5 or speed > 3.0:
        raise HTTPException(400, "Speed must be between 0.5 and 3.0")

    book_repo = SqlBookRepository(get_db_engine())
    if not book_repo.get_book(book_id):
        raise HTTPException(404, f"Book ID {book_id} not found")

    sentence = next(
        (s for s in book_repo.get_book_sentences(book_id) if s.sentence_index == sentence_index),
        None,
    )
    if not sentence:
        raise HTTPException(404, f"Sentence {sentence_index} not found for book {book_id}")

    voice_name = voice or load_app_settings(SqlSettingsRepository(get_db_engine())).default_voice
    try:
        path, _ = get_or_create_audio(
            get_db_engine(), book_id, sentence.text_content, voice_name, speed
        )
    except QuotaExceededError:
        raise
    except Exception as exc:
        logger.error(f"Failed to synthesize audio for book {book_id} sentence {sentence_index}: {exc}")
        raise HTTPException(500, f"Speech synthesis failed: {exc}") from exc
    return FileResponse(path, media_type=_media_type(path), headers=_AUDIO_HEADERS)


@router.get("/bookmarks/{book_id}", response_model=BookmarkResponse)
def get_bookmark(book_id: int) -> BookmarkResponse:
    """Retrieve saved bookmark for a book."""
    bookmark = SqlBookmarkRepository(get_db_engine()).get_bookmark(book_id)
    if not bookmark:
        return BookmarkResponse(
            book_id=book_id,
            current_chapter=1,
            current_sentence_index=0,
            completion_percentage=0.0,
            last_read_at=None,
        )

    last_read = bookmark.last_read_at
    last_read_str = (
        last_read.isoformat() if isinstance(last_read, datetime) else (str(last_read) if last_read else None)
    )
    return BookmarkResponse(
        book_id=bookmark.book_id,
        current_chapter=bookmark.current_chapter,
        current_sentence_index=bookmark.current_sentence_index,
        completion_percentage=bookmark.completion_percentage,
        last_read_at=last_read_str,
    )


@router.post("/bookmarks")
def update_bookmark(req: BookmarkUpdateRequest) -> dict[str, str]:
    """Update bookmark reading position."""
    SqlBookmarkRepository(get_db_engine()).update_bookmark(
        book_id=req.book_id,
        chapter_idx=req.current_chapter,
        sentence_idx=req.current_sentence_index,
        percentage=req.completion_percentage,
    )
    return {"status": "updated"}


@router.post("/sessions", status_code=201, response_model=ReadingSessionResponse)
def record_session(req: ReadingSessionCreateRequest) -> ReadingSessionResponse:
    """Record a completed reading session."""
    session_repo = SqlSessionRepository(get_db_engine())

    session = ReadingSession(
        book_id=req.book_id,
        start_time=datetime.fromisoformat(req.start_time.replace("Z", "+00:00")),
        end_time=datetime.fromisoformat(req.end_time.replace("Z", "+00:00")),
        duration_seconds=int(req.duration_seconds),
        sentences_read=req.sentences_read,
        words_read=req.words_read,
    )
    session_id = session_repo.record_session(session)

    return ReadingSessionResponse(
        id=session_id,
        book_id=session.book_id,
        duration_seconds=session.duration_seconds,
        sentences_read=session.sentences_read,
        words_read=session.words_read,
        created_at=datetime.utcnow().isoformat(),
    )
