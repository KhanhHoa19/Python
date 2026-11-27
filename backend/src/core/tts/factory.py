"""Text-to-Speech factory with provider resolution and mock injection."""

from __future__ import annotations

import os

from src.core.config import get_settings
from src.core.tts.base import TTSProvider


class TTSFactory:
    """Resolves and instantiates the active speech synthesis provider."""

    @classmethod
    def create_provider(
        cls,
        provider_name: str | None = None,
        voice: str | None = None,
    ) -> TTSProvider:
        """
        Instantiate the requested or configured TTS provider.

        If environment variable MOCK_TTS=true or TESTING=true is present,
        MockTTSProvider is injected to guarantee zero external network calls.
        """
        cfg = get_settings()

        # Check for automated test environment
        if os.getenv("MOCK_TTS", "false").lower() in ("true", "1", "yes") or os.getenv("TESTING") == "true":
            from tests.conftest import MockTTSProvider
            return MockTTSProvider()

        name = (provider_name or cfg.tts_provider).lower()
        default_voice = voice or cfg.effective_default_voice

        if name == "mock":
            from src.core.tts.mock_adapter import MockProvider
            return MockProvider(
                default_voice=voice or "mock-vi-female",
                latency_seconds=cfg.mock_latency_seconds,
                jitter_seconds=cfg.mock_jitter_seconds,
                error_rate=cfg.mock_error_rate,
                seed=cfg.mock_seed,
            )

        if name == "heygen":
            from src.core.tts.heygen_adapter import HeyGenProvider
            return HeyGenProvider(default_voice=voice or cfg.heygen_default_voice)

        if name in ("edge", "edge-tts", "edgetts"):
            from src.core.tts.edge_tts_adapter import EdgeTTSProvider
            return EdgeTTSProvider(default_voice=default_voice)

        elif name in ("openai", "openai-tts"):
            from src.core.tts.openai_adapter import OpenAITTSProvider
            return OpenAITTSProvider(default_voice=default_voice)

        else:
            from src.core.tts.edge_tts_adapter import EdgeTTSProvider
            return EdgeTTSProvider(default_voice=default_voice)
