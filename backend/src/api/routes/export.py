"""Export API router: merge a book's sentence audio into one downloadable file."""

from __future__ import annotations

import re
import unicodedata

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from src.api.schemas.export_schemas import (
    ExportEstimateResponse,
    ExportJobResponse,
    ExportRequest,
)
from src.core.app_settings import load_app_settings
from src.core.audio.export import ExportJob, create_job, get_job, run_export
from src.core.models.book import BookSentence
from src.core.player.audio_service import is_cached
from src.core.storage.db import get_db_engine
from src.core.storage.repositories import SqlBookRepository, SqlSettingsRepository

router = APIRouter(tags=["export"])

_WORDS_PER_MINUTE = 150.0


def _slug(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", ascii_title).strip("-").lower() or "audiobook"


def _select(book_id: int, from_index: int, to_index: int | None) -> tuple[SqlBookRepository, str, list[BookSentence]]:
    repo = SqlBookRepository(get_db_engine())
    book = repo.get_book(book_id)
    if not book:
        raise HTTPException(404, f"Book {book_id} not found")
    sentences = [
        s for s in repo.get_book_sentences(book_id)
        if s.sentence_index >= from_index and (to_index is None or s.sentence_index <= to_index)
    ]
    if not sentences:
        raise HTTPException(400, "No sentences in the selected range.")
    return repo, book.title, sentences


def _job_response(job: ExportJob) -> ExportJobResponse:
    return ExportJobResponse(
        job_id=job.job_id, status=job.status, done=job.done, total=job.total,  # type: ignore[arg-type]
        file_name=job.file_name or None, error=job.error,
    )


@router.get("/books/{book_id}/export/estimate", response_model=ExportEstimateResponse)
def estimate_export(
    book_id: int, from_index: int = 0, to_index: int | None = None, voice: str | None = None, speed: float = 1.0
) -> ExportEstimateResponse:
    _, _, sentences = _select(book_id, from_index, to_index)
    engine = get_db_engine()
    settings_repo = SqlSettingsRepository(engine)
    app_settings = load_app_settings(settings_repo)
    voice_name = voice or app_settings.default_voice

    to_synth = cached = 0
    for s in sentences:
        if is_cached(book_id, s.text_content, voice_name, speed):
            cached += len(s.text_content)
        else:
            to_synth += len(s.text_content)
    words = sum(s.word_count for s in sentences)
    return ExportEstimateResponse(
        sentences=len(sentences), words=words, estimated_minutes=round(words / _WORDS_PER_MINUTE, 1),
        chars_to_synthesize=to_synth, chars_cached=cached, daily_limit=app_settings.daily_char_limit,
        chars_used_today=settings_repo.chars_used_today(),
    )


@router.post("/books/{book_id}/export", status_code=202, response_model=ExportJobResponse)
def start_export(book_id: int, req: ExportRequest, background: BackgroundTasks) -> ExportJobResponse:
    _, title, sentences = _select(book_id, req.from_index, req.to_index)
    engine = get_db_engine()
    voice = req.voice or load_app_settings(SqlSettingsRepository(engine)).default_voice
    job = create_job(book_id, total=len(sentences))
    background.add_task(run_export, engine, job, sentences, voice, req.speed, req.format, _slug(title))
    return _job_response(job)


@router.get("/exports/{job_id}", response_model=ExportJobResponse)
def get_export_status(job_id: str) -> ExportJobResponse:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, f"Export job {job_id} not found")
    return _job_response(job)


@router.get("/exports/{job_id}/file")
def download_export(job_id: str) -> FileResponse:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, f"Export job {job_id} not found")
    if job.status != "done" or job.file_path is None or not job.file_path.exists():
        raise HTTPException(409, "Export is not finished.")
    return FileResponse(job.file_path, filename=job.file_name)
