"""Producer-consumer sentence playback engine (no UI code, no Tk).

Producer thread: fetches audio for upcoming sentences into a bounded queue.
Consumer thread: takes items off the queue and plays them one after another.

Every `start()` creates a fresh generation (own queue + stop event). Stopping simply signals the
old generation, so a producer stuck in a slow HTTP call never blocks the UI and can never
feed stale audio to the new playback.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from api_client import ApiError
from player.audio_output import AudioOutput

logger = logging.getLogger(__name__)

FetchAudio = Callable[[int], tuple[bytes, str]]

_POLL_SECONDS = 0.02


@dataclass
class EngineCallbacks:
    """Called from engine threads. Implementations must hand off to the UI thread themselves."""

    on_start: Callable[[int], None] = lambda index: None
    on_end: Callable[[int, float], None] = lambda index, seconds: None  # index, audio length
    on_skip: Callable[[int, str], None] = lambda index, message: None
    on_finished: Callable[[], None] = lambda: None
    on_fatal: Callable[[str], None] = lambda message: None


@dataclass
class _Generation:
    stop: threading.Event = field(default_factory=threading.Event)
    items: queue.Queue = field(default_factory=queue.Queue)


class PlaybackEngine:
    def __init__(self, fetch: FetchAudio, output: AudioOutput, total: int,
                 callbacks: EngineCallbacks, prefetch: int = 2):
        self._fetch = fetch
        self._output = output
        self._total = total
        self._callbacks = callbacks
        self._prefetch = max(1, prefetch)
        self._gen: _Generation | None = None
        self._lock = threading.Lock()
        self._paused = False
        self._last_latency_ms = 0.0

    # -- public API -----------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._gen is not None and not self._gen.stop.is_set()

    @property
    def is_paused(self) -> bool:
        return self.is_running and self._paused

    @property
    def buffered(self) -> int:
        gen = self._gen
        return gen.items.qsize() if gen else 0

    @property
    def prefetch(self) -> int:
        return self._prefetch

    @property
    def last_latency_ms(self) -> float:
        return self._last_latency_ms

    def start(self, index: int) -> None:
        """(Re)start playback from sentence `index`, dropping anything buffered."""
        self.stop()
        if not 0 <= index < self._total:
            return
        gen = _Generation(items=queue.Queue(maxsize=self._prefetch))
        with self._lock:
            self._gen = gen
            self._paused = False
        threading.Thread(target=self._produce, args=(gen, index), daemon=True, name="tts-producer").start()
        threading.Thread(target=self._consume, args=(gen,), daemon=True, name="tts-consumer").start()

    def pause(self) -> None:
        if self.is_running and not self._paused:
            self._paused = True
            self._output.pause()

    def resume(self) -> None:
        if self.is_running and self._paused:
            self._paused = False
            self._output.resume()

    def stop(self) -> None:
        with self._lock:
            gen, self._gen, self._paused = self._gen, None, False
            if gen is not None:
                gen.stop.set()
                self._output.stop()

    # -- threads --------------------------------------------------------------------

    def _put(self, gen: _Generation, item: tuple) -> bool:
        while not gen.stop.is_set():
            try:
                gen.items.put(item, timeout=_POLL_SECONDS)
                return True
            except queue.Full:
                continue
        return False

    def _fetch_with_retry(self, index: int) -> tuple[bytes, str]:
        try:
            return self._fetch(index)
        except ApiError as exc:
            if exc.is_quota_error or exc.is_connection_error:
                raise
            logger.warning("Sentence %s failed (%s), retrying once", index, exc)
            return self._fetch(index)

    def _produce(self, gen: _Generation, first_index: int) -> None:
        for index in range(first_index, self._total):
            if gen.stop.is_set():
                return
            started = time.perf_counter()
            try:
                data, ext = self._fetch_with_retry(index)
            except ApiError as exc:
                if exc.is_quota_error or exc.is_connection_error:
                    self._put(gen, ("fatal", index, exc.message))
                    return
                if not self._put(gen, ("skip", index, exc.message)):
                    return
                continue
            except Exception as exc:  # never let the producer die silently
                logger.exception("Producer crashed")
                self._put(gen, ("fatal", index, str(exc)))
                return
            self._last_latency_ms = (time.perf_counter() - started) * 1000.0
            if not self._put(gen, ("audio", index, data, ext)):
                return
        self._put(gen, ("end",))

    def _consume(self, gen: _Generation) -> None:
        while not gen.stop.is_set():
            try:
                item = gen.items.get(timeout=_POLL_SECONDS)
            except queue.Empty:
                continue
            kind = item[0]
            if kind == "audio":
                _, index, data, ext = item
                if not self._play(gen, index, data, ext):
                    return
            elif kind == "skip":
                self._callbacks.on_skip(item[1], item[2])
            elif kind == "fatal":
                self._finish(gen)
                self._callbacks.on_fatal(item[2])
                return
            elif kind == "end":
                self._finish(gen)
                self._callbacks.on_finished()
                return

    def _play(self, gen: _Generation, index: int, data: bytes, ext: str) -> bool:
        with self._lock:  # guards against a stale generation starting a sound after stop()
            if gen.stop.is_set():
                return False
            try:
                length = self._output.play(data, ext)
            except Exception as exc:
                logger.exception("Audio output failed")
                gen.stop.set()
                self._gen = None
                self._callbacks.on_fatal(f"Không phát được âm thanh: {exc}")
                return False
        self._callbacks.on_start(index)
        while self._output.is_busy() and not gen.stop.is_set():
            time.sleep(_POLL_SECONDS)
        if gen.stop.is_set():
            return False
        self._callbacks.on_end(index, length)
        return True

    def _finish(self, gen: _Generation) -> None:
        with self._lock:
            gen.stop.set()
            if self._gen is gen:
                self._gen = None
                self._paused = False
