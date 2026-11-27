"""Voices API router: list, preview, clone (with consent) and delete custom voices."""

from __future__ import annotations

import io
import logging
import uuid
import wave
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from src.api.deps import check_voice_access, current_user
from src.api.schemas.voice_schemas import VoiceListResponse, VoiceRenameRequest, VoiceResponse
from src.core.auth.users import User
from src.core.config import get_settings
from src.core.player.audio_service import get_or_create_audio
from src.core.storage.db import get_db_engine
from src.core.storage.repositories import SqlSettingsRepository, SqlVoiceRepository
from src.core.tts.base import TTSProviderError
from src.core.tts.factory import TTSFactory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voices"])

_SAMPLE_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg"}
_MAX_SAMPLE_BYTES = 10 * 1024 * 1024
_PREVIEW_TEXT = "Xin chào, đây là giọng đọc thử."


@router.get("", response_model=VoiceListResponse)
def list_voices(user: User = Depends(current_user)) -> VoiceListResponse:
    """Provider voices plus the custom voices this user may use (their own and public ones)."""
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
            consent_at=v["consent_at"], is_public=v["is_public"], is_mine=v["owner_id"] == user.id,
        )
        for v in SqlVoiceRepository(get_db_engine()).list_voices(user.id)
    ]
    # Providers such as HeyGen also list EVERY voice cloned in the shared account: keep only the app's own
    # entries for what this user may use, and hide the clones that belong to other people.
    custom_ids = {v["voice_id"] for v in SqlVoiceRepository(get_db_engine()).list_voices()}
    voices = [v for v in voices if v.voice_id not in custom_ids]
    return VoiceListResponse(
        provider=provider.provider_name,
        supports_cloning=provider.supports_cloning,
        clone_sample_seconds=provider.clone_sample_seconds,
        voices=custom + voices,
        warning=warning,
        my_voice_count=SqlVoiceRepository(get_db_engine()).count_owned(user.id),
        max_voices=None if user.is_admin else get_settings().max_voices_per_user,
        system_default_voice=SqlSettingsRepository(get_db_engine()).get("system_default_voice") or "",
    )


@router.post("/clone", status_code=201, response_model=VoiceResponse)
def clone_voice(
    sample: UploadFile = File(...),
    name: str = Form(..., min_length=1, max_length=100),
    language: str = Form("vi"),
    gender: Literal["male", "female"] | None = Form(None),
    consent: bool = Form(False),
    user: User = Depends(current_user),
) -> VoiceResponse:
    """Create a custom voice from a 5-15 second sample. Requires explicit consent."""
    if not consent:
        raise HTTPException(400, "Consent is required to clone a voice.")

    provider = TTSFactory.create_provider()
    if not provider.supports_cloning:
        raise HTTPException(501, f"Provider '{provider.provider_name}' does not support voice cloning.")
    limit = get_settings().max_voices_per_user
    if not user.is_admin and SqlVoiceRepository(get_db_engine()).count_owned(user.id) >= limit:
        # The provider account (and its daily clone allowance) is shared by every user.
        raise HTTPException(403, f"You can keep at most {limit} cloned voices. Delete one first.")

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
        low, high = provider.clone_sample_seconds
        if not low <= seconds <= high:
            raise HTTPException(400, f"Sample must be {low:g}-{high:g} seconds long.")

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
        owner_id=user.id, is_public=False,
    )
    return VoiceResponse(
        voice_id=voice_id, display_name=name.strip(), provider=provider.provider_name,
        language=language, gender=gender, is_custom=True, consent_at=consent_at.isoformat(), is_mine=True,
    )


@router.patch("/{voice_id}", response_model=VoiceResponse)
def rename_voice(voice_id: str, req: VoiceRenameRequest, user: User = Depends(current_user)) -> VoiceResponse:
    """Rename a cloned voice. Only the owner (or an admin, for a public voice) may."""
    repo = SqlVoiceRepository(get_db_engine())
    voice = repo.get_voice(voice_id)
    if voice is None or not (voice["is_public"] or voice["owner_id"] == user.id):
        raise HTTPException(404, f"Voice '{voice_id}' not found")
    if voice["owner_id"] != user.id and not user.is_admin:
        raise HTTPException(403, "You cannot rename this voice.")
    repo.rename_voice(voice_id, req.display_name)
    return VoiceResponse(
        voice_id=voice_id, display_name=req.display_name, provider=voice["provider"], language=voice["language"],
        gender=voice["gender"], style=voice["style"], is_custom=True, consent_at=voice["consent_at"],
        is_public=voice["is_public"], is_mine=voice["owner_id"] == user.id,
    )


@router.delete("/{voice_id}", status_code=204)
def delete_voice(voice_id: str, user: User = Depends(current_user)) -> None:
    """Delete a custom voice and its stored sample. Only the owner (or an admin, for a public voice) may."""
    repo = SqlVoiceRepository(get_db_engine())
    voice = repo.get_voice(voice_id)
    if voice is None or not (voice["is_public"] or voice["owner_id"] == user.id):
        raise HTTPException(404, f"Voice '{voice_id}' not found")
    if voice["owner_id"] != user.id and not user.is_admin:
        raise HTTPException(403, "You cannot delete this voice.")
    try:
        TTSFactory.create_provider().delete_voice(voice_id)  # free the provider-side clone slot too
    except TTSProviderError as exc:
        raise HTTPException(502, f"Could not delete the voice at the provider: {exc}") from exc
    repo.delete_voice(voice_id)
    if voice["sample_path"]:
        Path(voice["sample_path"]).unlink(missing_ok=True)


@router.get("/{voice_id}/preview")
def preview_voice(voice_id: str, user: User = Depends(current_user)) -> FileResponse:
    """Return a short audio sample of a voice."""
    check_voice_access(get_db_engine(), voice_id, user)
    try:
        path, _ = get_or_create_audio(get_db_engine(), 0, _PREVIEW_TEXT, voice_id, 1.0)
    except TTSProviderError as exc:
        raise HTTPException(502, f"Preview failed: {exc}") from exc
    return FileResponse(path, media_type=f"audio/{path.suffix.lstrip('.').replace('mp3', 'mpeg')}")
