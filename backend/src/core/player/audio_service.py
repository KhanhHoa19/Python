"""Shared audio retrieval: disk cache first, then provider synthesis with a daily character quota."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import Engine

from src.core.player.cache_manager import AudioCacheManager, voice_provider_hint
from src.core.storage.repositories import SqlSettingsRepository
from src.core.tts.base import TTSProvider
from src.core.tts.factory import TTSFactory
from src.core.tts.speech_text import prepare_speech_text

logger = logging.getLogger(__name__)


class QuotaExceededError(Exception):
    """Raised when the daily character limit would be exceeded by a new synthesis call."""


def active_provider(voice: str | None = None) -> TTSProvider:
    """The TTS provider selected in the configuration (one place, so callers and tests agree)."""
    return TTSFactory.create_provider(voice=voice)


def find_cached_audio(
    cache: AudioCacheManager, cache_scope: int, text: str, voice: str, speed: float, provider: TTSProvider
) -> Path | None:
    """Cached audio for this text/voice/speed made by `provider` (and its model), or None.

    Audio cached before keys carried a provider has the old key. It is adopted (renamed to the
    new key) when the voice id clearly belongs to the active provider; that way switching to
    provider-aware keys does not throw away, or re-pay for, audio you already have.
    """
    key = AudioCacheManager.compute_key(text, voice, speed, provider.cache_namespace)
    hit = cache.get_cached_audio(book_id=cache_scope, key=key)
    if hit and Path(hit).exists():
        return Path(hit)
    if voice_provider_hint(voice) != provider.provider_name:
        return None
    legacy = cache.get_cached_audio(book_id=cache_scope, key=AudioCacheManager.compute_key(text, voice, speed))
    if legacy and Path(legacy).exists():
        try:
            adopted = cache.adopt(cache_scope, Path(legacy), key)
        except OSError:  # another request adopted it first
            return cache.get_cached_audio(book_id=cache_scope, key=key)
        logger.info("Adopted legacy cache entry for voice %s into %s", voice, provider.cache_namespace)
        return adopted
    return None


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
    text = prepare_speech_text(text)  # the voice must not spell ALL-CAPS words; also keys the cache by what is spoken
    cache = AudioCacheManager()
    tts = provider or active_provider(voice)
    cached = find_cached_audio(cache, cache_scope, text, voice, speed, tts)
    if cached:
        return cached, True

    settings_repo = SqlSettingsRepository(engine)
    limit = int(settings_repo.get("daily_char_limit", "0") or 0)  # system-wide, set by an admin
    if limit > 0 and settings_repo.chars_used_today() + len(text) > limit:
        raise QuotaExceededError("Daily character limit reached.")

    result = tts.synthesize(text=text, voice=voice, speed=speed)
    key = AudioCacheManager.compute_key(text, voice, speed, tts.cache_namespace)
    saved = cache.save_audio(
        book_id=cache_scope, key=key, audio_bytes=result.audio_bytes, ext=result.audio_format or "mp3"
    )
    settings_repo.add_chars_used(len(text))
    return saved, False


def is_cached(
    cache_scope: int, text: str, voice: str, speed: float = 1.0, provider: TTSProvider | None = None
) -> bool:
    """True if audio for this text/voice/speed from the active provider is already cached."""
    tts = provider or active_provider(voice)
    return find_cached_audio(AudioCacheManager(), cache_scope, prepare_speech_text(text), voice, speed, tts) is not None
