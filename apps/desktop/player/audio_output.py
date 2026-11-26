"""Audio output abstraction so the playback engine can be tested without a sound card."""

from __future__ import annotations

import io
import threading
from typing import Any, Protocol


class AudioOutput(Protocol):
    """One sound at a time. All methods must be safe to call from any thread."""

    def play(self, data: bytes, ext: str) -> float:
        """Start playing `data` (replacing anything playing) and return its length in seconds."""
        ...

    def is_busy(self) -> bool:
        """True while a sound is playing or paused."""
        ...

    def pause(self) -> None: ...

    def resume(self) -> None: ...

    def stop(self) -> None: ...

    def close(self) -> None: ...


class PygameOutput:
    """`pygame.mixer` implementation. The mixer is initialised lazily on first use."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._channel: Any = None
        self._ready = False

    def _ensure_mixer(self) -> None:
        import pygame

        if not self._ready:
            pygame.mixer.init()
            self._ready = True

    def play(self, data: bytes, ext: str) -> float:
        import pygame

        with self._lock:
            self._ensure_mixer()
            sound = pygame.mixer.Sound(file=io.BytesIO(data))
            self._channel = sound.play()
            return float(sound.get_length())

    def is_busy(self) -> bool:
        with self._lock:
            return bool(self._channel is not None and self._channel.get_busy())

    def pause(self) -> None:
        with self._lock:
            if self._channel is not None:
                self._channel.pause()

    def resume(self) -> None:
        with self._lock:
            if self._channel is not None:
                self._channel.unpause()

    def stop(self) -> None:
        with self._lock:
            if self._channel is not None:
                self._channel.stop()
            self._channel = None

    def close(self) -> None:
        import pygame

        with self._lock:
            if self._ready:
                pygame.mixer.quit()
                self._ready = False
            self._channel = None
