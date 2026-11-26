"""Shared audio retrieval: disk cache first, then provider synthesis with a daily character quota."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import Engine

from src.core.app_settings import load_app_settings
from src.core.player.cache_manager import AudioCacheManager
from src.core.storage.repositories import SqlSettingsRepository
from src.core.tts.base import TTSProvider
from src.core.tts.factory import TTSFactory

logger = logging.getLogger(__name__)


class QuotaExceededError(Exception):
    """Raised when the daily character limit would be exceeded by a new synthesis call."""


def get_or_create_audio(
    engine: Engine,
    cache_scope: int,
    text: str,
    voice: str,
    speed: float = 1.0,
    provider: TTSProvider | None = None,
) -> tuple[Path, bool]:
    """Return (audio_path, from_cache). `cache_scope` is the book id (0 for non-book audio).

    Raises:
        QuotaExceededError: if synthesizing would exceed the configured daily character limit.
        TTSProviderError: if the provider fails.
    """
    cache = AudioCacheManager()
    key = AudioCacheManager.compute_key(text, voice, speed)
    cached = cache.get_cached_audio(book_id=cache_scope, key=key)
    if cached and Path(cached).exists():
        return Path(cached), True

    settings_repo = SqlSettingsRepository(engine)
    limit = load_app_settings(settings_repo).daily_char_limit
    if limit > 0 and settings_repo.chars_used_today() + len(text) > limit:
        raise QuotaExceededError("Daily character limit reached.")

    tts = provider or TTSFactory.create_provider(voice=voice)
    result = tts.synthesize(text=text, voice=voice, speed=speed)
    saved = cache.save_audio(
        book_id=cache_scope, key=key, audio_bytes=result.audio_bytes, ext=result.audio_format or "mp3"
    )
    settings_repo.add_chars_used(len(text))
    return saved, False


def is_cached(cache_scope: int, text: str, voice: str, speed: float = 1.0) -> bool:
    """True if audio for this text/voice/speed already exists in the cache."""
    key = AudioCacheManager.compute_key(text, voice, speed)
    return AudioCacheManager().get_cached_audio(book_id=cache_scope, key=key) is not None
