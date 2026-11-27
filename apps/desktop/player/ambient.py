"""Background sound under the narration: loops while the reader plays, at its own volume.

UI-free so it can be tested with a fake output. The audio file comes from the server's library
(Quản Trị › Âm thanh nền); it is downloaded once per track and kept in memory."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

FetchTrack = Callable[[int], tuple[bytes, str]]


class AmbientPlayer:
    def __init__(self, output: Any, fetch: FetchTrack | None = None):
        self._output = output
        self._fetch = fetch
        self.track_id = 0  # 0 = no background sound
        self.volume = 0.4
        self._fade = 1.0  # the sleep timer's fade-out also lowers the background
        self._playing = False
        self._started_id = 0  # the track currently loaded in the output channel
        self._cache: dict[int, tuple[bytes, str]] = {}
        self._loading: int | None = None
        self._lock = threading.Lock()

    # -- configuration ------------------------------------------------------------------------

    def configure(self, track_id: int, volume: float) -> None:
        """Apply the user's settings (called at start-up and whenever they change)."""
        with self._lock:
            changed = track_id != self.track_id
            self.track_id, self.volume = track_id, min(max(volume, 0.0), 1.0)
            if changed and self._started_id:
                self._output.stop_ambient()
                self._started_id = 0
        self._sync()

    def set_playing(self, playing: bool) -> None:
        """The reader started or stopped speaking: the background follows."""
        self._playing = playing
        self._sync()

    def set_fade(self, factor: float) -> None:
        self._fade = min(max(factor, 0.0), 1.0)
        if self._started_id:
            self._output.set_ambient_volume(self.volume * self._fade)

    def shutdown(self) -> None:
        self._playing = False
        self._output.stop_ambient()
        self._started_id = 0

    # -- internals --------------------------------------------------------------------------------

    def _sync(self) -> None:
        with self._lock:
            wanted = self._playing and self.track_id != 0
            if not wanted:
                if self._started_id:
                    self._output.pause_ambient()
                return
            if self._started_id == self.track_id:
                self._output.set_ambient_volume(self.volume * self._fade)
                self._output.resume_ambient()
                return
            if self.track_id in self._cache:
                self._start(self.track_id)
                return
            if self._loading == self.track_id or self._fetch is None:
                return
            self._loading = self.track_id
        threading.Thread(target=self._download, args=(self.track_id,), daemon=True).start()

    def _start(self, track_id: int) -> None:
        data, ext = self._cache[track_id]
        self._output.play_ambient(data, ext, self.volume * self._fade)
        self._started_id = track_id

    def _download(self, track_id: int) -> None:
        try:
            assert self._fetch is not None
            item = self._fetch(track_id)
        except Exception:  # a missing sound must never stop the reading
            logger.warning("Could not load background sound %s", track_id, exc_info=True)
            with self._lock:
                self._loading = None
            return
        with self._lock:
            self._cache[track_id] = item
            self._loading = None
            if self._playing and self.track_id == track_id and self._started_id != track_id:
                self._start(track_id)
