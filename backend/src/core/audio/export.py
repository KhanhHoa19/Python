"""Concatenate sentence audio into one file; tracks background export jobs in memory."""

from __future__ import annotations

import io
import threading
import uuid
import wave
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine

from src.core.config import get_settings
from src.core.models.book import BookSentence
from src.core.player.audio_service import QuotaExceededError, get_or_create_audio
from src.core.tts.base import TTSProviderError


@dataclass
class ExportJob:
    job_id: str
    book_id: int
    total: int
    done: int = 0
    status: str = "running"  # running | done | failed
    error: str | None = None
    file_path: Path | None = None
    file_name: str = ""


_JOBS: dict[str, ExportJob] = {}
_JOBS_LOCK = threading.Lock()


def create_job(book_id: int, total: int) -> ExportJob:
    job = ExportJob(job_id=uuid.uuid4().hex, book_id=book_id, total=total)
    with _JOBS_LOCK:
        _JOBS[job.job_id] = job
    return job


def get_job(job_id: str) -> ExportJob | None:
    with _JOBS_LOCK:
        return _JOBS.get(job_id)


def _concat_wav(paths: list[Path]) -> bytes:
    out = io.BytesIO()
    params = None
    with wave.open(out, "wb") as target:
        for path in paths:
            with wave.open(str(path), "rb") as src:
                if params is None:
                    params = src.getparams()
                    target.setparams(params)
                elif src.getparams()[:3] != params[:3]:
                    raise ValueError("Audio segments have different WAV formats.")
                target.writeframes(src.readframes(src.getnframes()))
    return out.getvalue()


def _audio_with_retry(engine: Engine, book_id: int, text: str, voice: str, speed: float) -> Path:
    """One retry for transient provider errors (free TTS services drop requests now and then)."""
    try:
        return get_or_create_audio(engine, book_id, text, voice, speed)[0]
    except TTSProviderError:
        return get_or_create_audio(engine, book_id, text, voice, speed)[0]


def run_export(
    engine: Engine,
    job: ExportJob,
    sentences: list[BookSentence],
    voice: str,
    speed: float,
    fmt: str | None,
    slug: str,
) -> None:
    """Synthesize (or reuse cached) audio per sentence and write the merged file. Never raises."""
    try:
        paths: list[Path] = []
        for sentence in sentences:
            path = _audio_with_retry(engine, job.book_id, sentence.text_content, voice, speed)
            paths.append(path)
            job.done += 1

        ext = paths[0].suffix.lstrip(".").lower() if paths else "wav"
        if fmt and fmt.lower() != ext:
            raise ValueError(f"Provider audio is '{ext}', cannot export as '{fmt.lower()}'.")
        if any(p.suffix.lstrip(".").lower() != ext for p in paths):
            raise ValueError("Audio segments have mixed formats; clear the cache and retry.")

        data = _concat_wav(paths) if ext == "wav" else b"".join(p.read_bytes() for p in paths)
        out_dir = Path(get_settings().export_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        job.file_name = f"{slug}.{ext}"
        job.file_path = out_dir / f"{job.job_id}.{ext}"
        job.file_path.write_bytes(data)
        job.status = "done"
    except QuotaExceededError:
        job.status, job.error = "failed", "Daily character limit reached."
    except (TTSProviderError, ValueError, OSError, wave.Error) as exc:
        job.status, job.error = "failed", str(exc)
    except Exception as exc:  # background thread must not crash silently
        job.status, job.error = "failed", f"Unexpected error: {exc}"
