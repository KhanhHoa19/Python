"""Abstract Text-to-Speech (TTS) provider protocol and error hierarchy."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class TTSProviderError(Exception):
    """Base exception for speech synthesis errors."""
    pass


class RateLimitError(TTSProviderError):
    """Raised when TTS provider rate limits or quotas are exceeded."""
    pass


@dataclass(frozen=True)
class VoiceInfo:
    """Describes a voice offered by a provider."""
    voice_id: str
    display_name: str
    language: str = ""
    gender: str | None = None
    style: str | None = None


@dataclass(frozen=True)
class AudioSynthesisResult:
    """Represents the output and performance metrics of a speech synthesis request."""
    audio_bytes: bytes
    audio_format: str  # e.g., "mp3", "wav"
    duration_seconds: float
    response_time_seconds: float
    cached: bool = False


class TTSProvider(ABC):
    """Abstract interface for all speech synthesis engines."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the unique identifier for the provider (e.g., 'edge-tts', 'openai')."""
        pass

    @property
    @abstractmethod
    def default_voice(self) -> str:
        """Return the default voice model identifier."""
        pass

    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
    ) -> AudioSynthesisResult:
        """
        Synthesize speech from input text synchronously or via internal event loop.

        Args:
            text: Plain text sentence to synthesize.
            voice: Voice identifier. If None, uses default_voice.
            speed: Speech rate multiplier (e.g. 0.75 - 2.0).

        Returns:
            AudioSynthesisResult containing audio data and generation metrics.

        Raises:
            TTSProviderError: When synthesis fails due to network or API error.
            RateLimitError: When API quota or rate limits are exceeded.
        """
        pass

    @property
    def supports_cloning(self) -> bool:
        """Whether this provider can create a custom voice from an audio sample."""
        return False

    def list_voices(self) -> list[VoiceInfo]:
        """Return the voices offered by the provider (empty if the provider cannot list them)."""
        return []

    def clone_voice(self, sample_path: str, name: str, language: str = "vi") -> str:
        """Create a custom voice from a sample file and return its voice_id."""
        raise TTSProviderError(f"Provider '{self.provider_name}' does not support voice cloning.")

    def verify(self) -> None:
        """Check credentials and connectivity by synthesizing a very short sentence.

        Raises:
            TTSProviderError: When the provider rejects the request or is unreachable.
        """
        self.synthesize("Xin chào.", voice=None, speed=1.0)
