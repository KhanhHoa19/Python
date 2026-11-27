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

    def set_volume(self, volume: float) -> None:
        """0.0-1.0. Applies to the sound playing now and to every later sound."""
        ...

    def pause(self) -> None: ...

    def resume(self) -> None: ...

    def stop(self) -> None: ...

    # A second, independent channel for the background sound: it loops until stopped and never replaces the voice.
    def play_ambient(self, data: bytes, ext: str, volume: float) -> None: ...

    def set_ambient_volume(self, volume: float) -> None: ...

    def pause_ambient(self) -> None: ...

    def resume_ambient(self) -> None: ...

    def stop_ambient(self) -> None: ...

    def close(self) -> None: ...


class PygameOutput:
    """`pygame.mixer` implementation. The mixer is initialised lazily on first use."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._channel: Any = None
        self._ready = False
        self._volume = 1.0
        self._ambient_sound: Any = None

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
            if self._channel is not None:
                self._channel.set_volume(self._volume)  # a new sound starts at full channel volume
            return float(sound.get_length())

    def is_busy(self) -> bool:
        with self._lock:
            return bool(self._channel is not None and self._channel.get_busy())

    def set_volume(self, volume: float) -> None:
        with self._lock:
            self._volume = min(max(volume, 0.0), 1.0)
            if self._channel is not None:
                self._channel.set_volume(self._volume)

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

    # -- background sound: reserved channel 0, so a voice `Sound.play()` never takes it ----------------

    def _ambient(self) -> Any:
        import pygame

        self._ensure_mixer()
        pygame.mixer.set_reserved(1)
        return pygame.mixer.Channel(0)

    def play_ambient(self, data: bytes, ext: str, volume: float) -> None:
        import pygame

        with self._lock:
            channel = self._ambient()
            self._ambient_sound = pygame.mixer.Sound(file=io.BytesIO(data))
            channel.set_volume(min(max(volume, 0.0), 1.0))
            channel.play(self._ambient_sound, loops=-1)

    def set_ambient_volume(self, volume: float) -> None:
        with self._lock:
            if self._ready:
                self._ambient().set_volume(min(max(volume, 0.0), 1.0))

    def pause_ambient(self) -> None:
        with self._lock:
            if self._ready:
                self._ambient().pause()

    def resume_ambient(self) -> None:
        with self._lock:
            if self._ready:
                self._ambient().unpause()

    def stop_ambient(self) -> None:
        with self._lock:
            if self._ready:
                self._ambient().stop()
            self._ambient_sound = None

    def close(self) -> None:
        import pygame

        with self._lock:
            if self._ready:
                pygame.mixer.quit()
                self._ready = False
            self._channel = None
