"""Offline mock TTS provider for development: silent WAV audio, fake voices and fake cloning."""

from __future__ import annotations

import hashlib
import io
import random
import time
import wave
from collections.abc import Callable

from src.core.tts.base import AudioSynthesisResult, TTSProvider, TTSProviderError, VoiceInfo

_WORDS_PER_SECOND = 2.5
_SAMPLE_RATE = 16000


_SHARED_RNG = random.Random()  # factory builds a provider per request; unseeded runs share one stream


class MockProvider(TTSProvider):
    """Generates silent WAV whose length scales with word count. Needs no network or key.

    Meant for development and for measuring the player: `latency_seconds` delays every call and
    `jitter_seconds` makes it vary (latency +/- jitter), and `error_rate` (0..1) makes that share of
    calls fail, like a flaky cloud service. With a `seed` both are reproducible.
    """

    def __init__(
        self,
        default_voice: str = "mock-vi-female",
        latency_seconds: float = 0.0,
        error_rate: float = 0.0,
        seed: int | None = None,
        sleep: Callable[[float], None] = time.sleep,
        jitter_seconds: float = 0.0,
    ):
        if latency_seconds < 0 or jitter_seconds < 0:
            raise ValueError("latency_seconds and jitter_seconds must be >= 0")
        if not 0.0 <= error_rate <= 1.0:
            raise ValueError("error_rate must be between 0 and 1")
        self._default_voice = default_voice
        self._latency = latency_seconds
        self._jitter = jitter_seconds
        self._error_rate = error_rate
        self._rng = random.Random(seed) if seed is not None else _SHARED_RNG
        self._sleep = sleep
        self._clones: list[VoiceInfo] = []

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def default_voice(self) -> str:
        return self._default_voice

    @property
    def supports_cloning(self) -> bool:
        return True

    def synthesize(self, text: str, voice: str | None = None, speed: float = 1.0) -> AudioSynthesisResult:
        if not text.strip():
            raise TTSProviderError("Cannot synthesize empty text.")
        start = time.perf_counter()
        if self._latency > 0 or self._jitter > 0:
            # uniform in [latency - jitter, latency + jitter], never negative
            self._sleep(max(0.0, self._latency + self._rng.uniform(-self._jitter, self._jitter)))
        if self._error_rate > 0 and self._rng.random() < self._error_rate:
            raise TTSProviderError("Simulated mock TTS failure")
        duration = max(0.3, len(text.split()) / _WORDS_PER_SECOND)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(_SAMPLE_RATE)
            wav.writeframes(b"\x00\x00" * int(duration * _SAMPLE_RATE))
        return AudioSynthesisResult(
            audio_bytes=buf.getvalue(),
            audio_format="wav",
            duration_seconds=duration,
            response_time_seconds=time.perf_counter() - start,
        )

    def list_voices(self) -> list[VoiceInfo]:
        return [
            VoiceInfo("mock-vi-female", "Mock Nữ (Bắc)", "vi-VN", "female", "kể chuyện"),
            VoiceInfo("mock-vi-male", "Mock Nam (Nam)", "vi-VN", "male", "tin tức"),
        ]

    def clone_voice(self, sample_path: str, name: str, language: str = "vi") -> str:
        digest = hashlib.sha256(f"{sample_path}:{name}".encode()).hexdigest()[:12]
        return f"mock-clone-{digest}"
