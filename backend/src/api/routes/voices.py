"""Voices API router: list, preview, clone (with consent) and delete custom voices."""

from __future__ import annotations

import io
import logging
import uuid
import wave
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from src.api.schemas.voice_schemas import VoiceListResponse, VoiceResponse
from src.core.config import get_settings
from src.core.player.audio_service import get_or_create_audio
from src.core.storage.db import get_db_engine
from src.core.storage.repositories import SqlVoiceRepository
from src.core.tts.base import TTSProviderError
from src.core.tts.factory import TTSFactory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voices"])

_SAMPLE_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg"}
_MAX_SAMPLE_BYTES = 10 * 1024 * 1024
_PREVIEW_TEXT = "Xin chào, đây là giọng đọc thử."


@router.get("", response_model=VoiceListResponse)
def list_voices() -> VoiceListResponse:
    """List provider voices plus the user's custom voices."""
    provider = TTSFactory.create_provider()
    warning: str | None = None
    voices: list[VoiceResponse] = []
    try:
        voices = [
            VoiceResponse(
                voice_id=v.voice_id, display_name=v.display_name, provider=provider.provider_name,
                language=v.language, gender=v.gender, style=v.style,
            )
            for v in provider.list_voices()
        ]
    except TTSProviderError as exc:
        warning = str(exc)

    custom = [
        VoiceResponse(
            voice_id=v["voice_id"], display_name=v["display_name"], provider=v["provider"],
            language=v["language"], gender=v["gender"], style=v["style"], is_custom=True,
            consent_at=v["consent_at"],
        )
        for v in SqlVoiceRepository(get_db_engine()).list_voices()
    ]
    return VoiceListResponse(
        provider=provider.provider_name,
        supports_cloning=provider.supports_cloning,
        voices=custom + voices,
        warning=warning,
    )


@router.post("/clone", status_code=201, response_model=VoiceResponse)
def clone_voice(
    sample: UploadFile = File(...),
    name: str = Form(..., min_length=1, max_length=100),
    language: str = Form("vi"),
    gender: Literal["male", "female"] | None = Form(None),
    consent: bool = Form(False),
) -> VoiceResponse:
    """Create a custom voice from a 5-15 second sample. Requires explicit consent."""
    if not consent:
        raise HTTPException(400, "Consent is required to clone a voice.")

    provider = TTSFactory.create_provider()
    if not provider.supports_cloning:
        raise HTTPException(501, f"Provider '{provider.provider_name}' does not support voice cloning.")

    ext = Path(sample.filename or "").suffix.lower()
    if ext not in _SAMPLE_EXTENSIONS:
        raise HTTPException(400, f"Unsupported sample format. Use: {', '.join(sorted(_SAMPLE_EXTENSIONS))}.")
    data = sample.file.read(_MAX_SAMPLE_BYTES + 1)
    if len(data) > _MAX_SAMPLE_BYTES:
        raise HTTPException(400, "Sample exceeds 10 MB.")
    if ext == ".wav":
        try:
            with wave.open(io.BytesIO(data), "rb") as wav:
                seconds = wav.getnframes() / float(wav.getframerate())
        except (wave.Error, EOFError, ZeroDivisionError) as exc:
            raise HTTPException(400, "Sample is not a valid WAV file.") from exc
        if not 5.0 <= seconds <= 15.0:
            raise HTTPException(400, "Sample must be 5-15 seconds long.")

    samples_dir = Path(get_settings().voice_samples_dir).resolve()
    samples_dir.mkdir(parents=True, exist_ok=True)
    sample_path = samples_dir / f"{uuid.uuid4().hex}{ext}"
    sample_path.write_bytes(data)

    try:
        voice_id = provider.clone_voice(str(sample_path), name.strip(), language)
    except TTSProviderError as exc:
        sample_path.unlink(missing_ok=True)
        raise HTTPException(502, f"Voice cloning failed: {exc}") from exc

    consent_at = datetime.now(UTC)
    SqlVoiceRepository(get_db_engine()).add_voice(
        voice_id=voice_id, provider=provider.provider_name, display_name=name.strip(),
        language=language, gender=gender, sample_path=str(sample_path), consent_at=consent_at,
    )
    return VoiceResponse(
        voice_id=voice_id, display_name=name.strip(), provider=provider.provider_name,
        language=language, gender=gender, is_custom=True, consent_at=consent_at.isoformat(),
    )


@router.delete("/{voice_id}", status_code=204)
def delete_voice(voice_id: str) -> None:
    """Delete a custom voice and its stored sample."""
    repo = SqlVoiceRepository(get_db_engine())
    voice = repo.get_voice(voice_id)
    if voice is None:
        raise HTTPException(404, f"Voice '{voice_id}' not found")
    repo.delete_voice(voice_id)
    if voice["sample_path"]:
        Path(voice["sample_path"]).unlink(missing_ok=True)


@router.get("/{voice_id}/preview")
def preview_voice(voice_id: str) -> FileResponse:
    """Return a short audio sample of a voice."""
    try:
        path, _ = get_or_create_audio(get_db_engine(), 0, _PREVIEW_TEXT, voice_id, 1.0)
    except TTSProviderError as exc:
        raise HTTPException(502, f"Preview failed: {exc}") from exc
    return FileResponse(path, media_type=f"audio/{path.suffix.lstrip('.').replace('mp3', 'mpeg')}")
