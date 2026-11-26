"""Audio notes API router: highlighted excerpts with a personal note and replayable audio."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.api.schemas.note_schemas import NoteCreateRequest, NoteResponse, NoteUpdateRequest
from src.core.app_settings import load_app_settings
from src.core.player.audio_service import get_or_create_audio
from src.core.storage.db import get_db_engine
from src.core.storage.repositories import (
    SqlBookRepository,
    SqlNoteRepository,
    SqlSettingsRepository,
)
from src.core.tts.base import TTSProviderError

router = APIRouter(tags=["notes"])


def _sentence_text(book_repo: SqlBookRepository, book_id: int, sentence_index: int) -> str | None:
    rows = book_repo.get_sentences(book_id, start_idx=sentence_index, limit=1)
    return rows[0].text_content if rows and rows[0].sentence_index == sentence_index else None


def _to_response(note: dict[str, Any], book_repo: SqlBookRepository) -> NoteResponse:
    text = _sentence_text(book_repo, note["book_id"], note["sentence_index"]) or ""
    return NoteResponse(**note, excerpt=text[note["start_offset"]:note["end_offset"]])


@router.get("", response_model=list[NoteResponse])
def list_notes(book_id: int | None = None) -> list[NoteResponse]:
    engine = get_db_engine()
    book_repo = SqlBookRepository(engine)
    return [_to_response(n, book_repo) for n in SqlNoteRepository(engine).list_notes(book_id)]


@router.post("", status_code=201, response_model=NoteResponse)
def create_note(req: NoteCreateRequest) -> NoteResponse:
    engine = get_db_engine()
    book_repo = SqlBookRepository(engine)
    if not book_repo.get_book(req.book_id):
        raise HTTPException(404, f"Book {req.book_id} not found")
    text = _sentence_text(book_repo, req.book_id, req.sentence_index)
    if text is None:
        raise HTTPException(404, f"Sentence {req.sentence_index} not found for book {req.book_id}")
    if req.start_offset >= req.end_offset or req.end_offset > len(text):
        raise HTTPException(400, "Selection offsets are outside the sentence.")

    repo = SqlNoteRepository(engine)
    note_id = repo.create_note(req.book_id, req.sentence_index, req.start_offset, req.end_offset, req.note_text)
    note = repo.get_note(note_id)
    assert note is not None
    return _to_response(note, book_repo)


@router.patch("/{note_id}", response_model=NoteResponse)
def update_note(note_id: int, req: NoteUpdateRequest) -> NoteResponse:
    engine = get_db_engine()
    repo = SqlNoteRepository(engine)
    if not repo.update_note_text(note_id, req.note_text):
        raise HTTPException(404, f"Note {note_id} not found")
    note = repo.get_note(note_id)
    assert note is not None
    return _to_response(note, SqlBookRepository(engine))


@router.delete("/{note_id}", status_code=204)
def delete_note(note_id: int) -> None:
    if not SqlNoteRepository(get_db_engine()).delete_note(note_id):
        raise HTTPException(404, f"Note {note_id} not found")


@router.get("/{note_id}/audio")
def get_note_audio(note_id: int, voice: str | None = None, speed: float = 1.0) -> FileResponse:
    """Audio of the highlighted excerpt (cached after the first synthesis)."""
    if not 0.5 <= speed <= 3.0:
        raise HTTPException(400, "Speed must be between 0.5 and 3.0")
    engine = get_db_engine()
    note = SqlNoteRepository(engine).get_note(note_id)
    if note is None:
        raise HTTPException(404, f"Note {note_id} not found")
    excerpt = _to_response(note, SqlBookRepository(engine)).excerpt
    if not excerpt.strip():
        raise HTTPException(404, "The sentence for this note no longer exists.")

    voice_name = voice or load_app_settings(SqlSettingsRepository(engine)).default_voice
    try:
        path, _ = get_or_create_audio(engine, note["book_id"], excerpt, voice_name, speed)
    except TTSProviderError as exc:
        raise HTTPException(502, f"Speech synthesis failed: {exc}") from exc
    return FileResponse(path, media_type=f"audio/{path.suffix.lstrip('.').replace('mp3', 'mpeg')}")
