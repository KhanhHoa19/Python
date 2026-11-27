"""Favourite quotes ("Trích dẫn yêu thích"): a highlighted excerpt or a whole sentence, with a feeling tag,
the sentences around it and a permanent copy of its audio. Stored in the audio_notes table."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse

from src.api.deps import check_voice_access, current_user, visible_book
from src.api.schemas.note_schemas import (
    EmotionTag,
    NoteCreateRequest,
    NoteResponse,
    NoteUpdateRequest,
)
from src.core.app_settings import load_app_settings
from src.core.audio.quotes import delete_quote_audio, quote_audio_path, save_quote_audio
from src.core.auth.users import User
from src.core.player.audio_service import QuotaExceededError, get_or_create_audio
from src.core.storage.db import get_db_engine
from src.core.storage.repositories import (
    SqlBookRepository,
    SqlNoteRepository,
    SqlSettingsRepository,
    SqlUserSettingsRepository,
)
from src.core.tts.base import TTSProviderError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["notes"])


def _sentence_text(book_repo: SqlBookRepository, book_id: int, sentence_index: int) -> str | None:
    rows = book_repo.get_sentences(book_id, start_idx=sentence_index, limit=1)
    return rows[0].text_content if rows and rows[0].sentence_index == sentence_index else None


def _to_response(note: dict[str, Any], book_repo: SqlBookRepository) -> NoteResponse:
    text = _sentence_text(book_repo, note["book_id"], note["sentence_index"]) or ""
    fields = {k: v for k, v in note.items() if k != "audio_path"}  # a server path is nobody's business
    return NoteResponse(**fields, excerpt=text[note["start_offset"]:note["end_offset"]],
                        has_audio=quote_audio_path(note["audio_path"]) is not None)


def _default_voice(engine: Any, user: User) -> str:
    return load_app_settings(SqlSettingsRepository(engine), SqlUserSettingsRepository(engine, user.id)).default_voice


def _save_audio(engine: Any, repo: SqlNoteRepository, note: dict[str, Any], excerpt: str, voice: str, user: User) -> None:
    """Keep a permanent copy of the quote's audio. A TTS failure or the daily limit never stops the quote from
    being saved: the audio is then made the first time it is played."""
    try:
        cached, _ = get_or_create_audio(engine, note["book_id"], excerpt, voice, 1.0)
        repo.set_audio(note["id"], save_quote_audio(cached, user.id), voice)
    except (TTSProviderError, QuotaExceededError, OSError) as exc:
        logger.warning("Quote %s saved without audio: %s", note["id"], exc)


@router.get("", response_model=list[NoteResponse])
def list_notes(
    book_id: int | None = None, emotion_tag: EmotionTag | None = None, user: User = Depends(current_user)
) -> list[NoteResponse]:
    engine = get_db_engine()
    book_repo = SqlBookRepository(engine)
    return [_to_response(n, book_repo) for n in SqlNoteRepository(engine, user.id).list_notes(book_id, emotion_tag)]


@router.post("", status_code=201, response_model=NoteResponse)
def create_note(req: NoteCreateRequest, response: Response, user: User = Depends(current_user)) -> NoteResponse:
    engine = get_db_engine()
    book_repo = SqlBookRepository(engine)
    visible_book(engine, req.book_id, user)
    text = _sentence_text(book_repo, req.book_id, req.sentence_index)
    if text is None:
        raise HTTPException(404, f"Sentence {req.sentence_index} not found for book {req.book_id}")
    start, end = (0, len(text)) if req.start_offset is None or req.end_offset is None else (req.start_offset, req.end_offset)
    if start >= end or end > len(text):
        raise HTTPException(400, "Selection offsets are outside the sentence.")
    check_voice_access(engine, req.voice, user)

    repo = SqlNoteRepository(engine, user.id)
    existing = repo.find_same(req.book_id, req.sentence_index, start, end)
    if existing is not None:  # tapping "Đánh dấu đoạn này" twice keeps one quote (and may add the tag or text)
        repo.update_note(existing["id"], note_text=req.note_text or None,
                         **({"emotion_tag": req.emotion_tag} if req.emotion_tag else {}))
        response.status_code = 200
        note = repo.get_note(existing["id"])
        assert note is not None
        return _to_response(note, book_repo)

    neighbours = {s.sentence_index: s.text_content for s in
                  book_repo.get_sentences(req.book_id, start_idx=max(req.sentence_index - 1, 0), limit=3)}
    voice = req.voice or _default_voice(engine, user)
    note_id = repo.create_note(
        req.book_id, req.sentence_index, start, end, req.note_text, req.emotion_tag,
        context_before=neighbours.get(req.sentence_index - 1, ""), context_after=neighbours.get(req.sentence_index + 1, ""),
        voice=voice,
    )
    note = repo.get_note(note_id)
    assert note is not None
    _save_audio(engine, repo, note, text[start:end], voice, user)
    note = repo.get_note(note_id)
    assert note is not None
    return _to_response(note, book_repo)


@router.patch("/{note_id}", response_model=NoteResponse)
def update_note(note_id: int, req: NoteUpdateRequest, user: User = Depends(current_user)) -> NoteResponse:
    engine = get_db_engine()
    repo = SqlNoteRepository(engine, user.id)
    changes: dict[str, Any] = {}
    if req.note_text is not None:
        changes["note_text"] = req.note_text
    if "emotion_tag" in req.model_fields_set:
        changes["emotion_tag"] = req.emotion_tag
    if not changes:
        raise HTTPException(400, "Send note_text and/or emotion_tag.")
    if not repo.update_note(note_id, **changes):
        raise HTTPException(404, f"Note {note_id} not found")
    note = repo.get_note(note_id)
    assert note is not None
    return _to_response(note, SqlBookRepository(engine))


@router.delete("/{note_id}", status_code=204)
def delete_note(note_id: int, user: User = Depends(current_user)) -> None:
    repo = SqlNoteRepository(get_db_engine(), user.id)
    note = repo.get_note(note_id)
    if note is None or not repo.delete_note(note_id):
        raise HTTPException(404, f"Note {note_id} not found")
    delete_quote_audio(note["audio_path"])


@router.get("/{note_id}/audio")
def get_note_audio(
    note_id: int, voice: str | None = None, speed: float = 1.0, user: User = Depends(current_user)
) -> FileResponse:
    """The quote's audio: its saved copy, or (if there is none yet) made now and saved. With `voice` or a
    non-default `speed` the audio is made from the cache instead and the saved copy is left alone."""
    if not 0.5 <= speed <= 3.0:
        raise HTTPException(400, "Speed must be between 0.5 and 3.0")
    engine = get_db_engine()
    check_voice_access(engine, voice, user)
    repo = SqlNoteRepository(engine, user.id)
    note = repo.get_note(note_id)
    if note is None:
        raise HTTPException(404, f"Note {note_id} not found")
    excerpt = _to_response(note, SqlBookRepository(engine)).excerpt
    if not excerpt.strip():
        raise HTTPException(404, "The sentence for this note no longer exists.")

    saved = quote_audio_path(note["audio_path"])
    if saved is not None and voice is None and speed == 1.0:
        return FileResponse(saved, media_type=f"audio/{saved.suffix.lstrip('.').replace('mp3', 'mpeg')}")
    voice_name = voice or note["voice"] or _default_voice(engine, user)
    try:
        path, _ = get_or_create_audio(engine, note["book_id"], excerpt, voice_name, speed)
        if voice is None and speed == 1.0:  # first play of a quote saved without audio: keep it from now on
            repo.set_audio(note_id, save_quote_audio(path, user.id), voice_name)
    except TTSProviderError as exc:
        raise HTTPException(502, f"Speech synthesis failed: {exc}") from exc
    return FileResponse(path, media_type=f"audio/{path.suffix.lstrip('.').replace('mp3', 'mpeg')}")
