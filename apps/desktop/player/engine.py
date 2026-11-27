"""Producer-consumer sentence playback engine (no UI code, no Tk).

Fetcher threads: download audio for upcoming sentences, `fetch_workers` at a time. Results are put
back into sentence order before they reach the queue, so slow or failed downloads never reorder
playback. At most `prefetch` sentences ahead of the one being played are requested.
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
    on_stop_point: Callable[[int], None] = lambda index: None  # playback stopped after sentence `stop_after`


@dataclass
class _Generation:
    stop: threading.Event = field(default_factory=threading.Event)
    items: queue.Queue = field(default_factory=queue.Queue)
    cond: threading.Condition = field(default_factory=threading.Condition)
    next_claim: int = 0  # next sentence a fetcher will download
    next_emit: int = 0  # next sentence to hand to the consumer (keeps order)
    taken: int = 0  # next sentence the consumer will take
    halted: bool = False  # a fatal error or the end was reached: fetchers must stop
    results: dict = field(default_factory=dict)  # index -> item waiting for its turn


class PlaybackEngine:
    def __init__(self, fetch: FetchAudio, output: AudioOutput, total: int,
                 callbacks: EngineCallbacks, prefetch: int = 2, fetch_workers: int = 1,
                 before_sentence: Callable[[int], bytes | None] | None = None):
        self._fetch = fetch
        self._output = output
        self._total = total
        self._callbacks = callbacks
        self._prefetch = max(1, prefetch)
        self._fetch_workers = max(1, fetch_workers)
        self._before_sentence = before_sentence  # returns a WAV (the chapter chime) to play before sentence `index`, or None
        self._gen: _Generation | None = None
        self._lock = threading.Lock()
        self._paused = False
        self._last_latency_ms = 0.0
        self.stop_after: int | None = None  # stop once this sentence has been played (sleep timer: end of chapter)
        self._sentence_length = 0.0
        self._sentence_started = 0.0
        self._paused_total = 0.0
        self._pause_started: float | None = None

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
    def fetch_workers(self) -> int:
        return self._fetch_workers

    @property
    def last_latency_ms(self) -> float:
        return self._last_latency_ms

    @property
    def sentence_length(self) -> float:
        """Length in seconds of the sentence being played (0 before the first one)."""
        return self._sentence_length

    def sentence_remaining(self) -> float:
        """Seconds of the current sentence still to play, not counting time spent paused."""
        now = self._pause_started if self._pause_started is not None else time.monotonic()
        return max(0.0, self._sentence_length - (now - self._sentence_started - self._paused_total))

    def start(self, index: int) -> None:
        """(Re)start playback from sentence `index`, dropping anything buffered."""
        self.stop()
        if not 0 <= index < self._total:
            return
        gen = _Generation(next_claim=index, next_emit=index, taken=index)
        with self._lock:
            self._gen = gen
            self._paused = False
        for number in range(self._fetch_workers):
            threading.Thread(target=self._fetcher, args=(gen,), daemon=True, name=f"tts-fetch-{number}").start()
        threading.Thread(target=self._consume, args=(gen,), daemon=True, name="tts-consumer").start()

    def pause(self) -> None:
        if self.is_running and not self._paused:
            self._paused = True
            self._pause_started = time.monotonic()
            self._output.pause()

    def resume(self) -> None:
        if self.is_running and self._paused:
            self._paused = False
            if self._pause_started is not None:
                self._paused_total += time.monotonic() - self._pause_started
                self._pause_started = None
            self._output.resume()

    def stop(self) -> None:
        with self._lock:
            gen, self._gen, self._paused = self._gen, None, False
            if gen is not None:
                gen.stop.set()
                self._output.stop()

    # -- threads --------------------------------------------------------------------

    def _fetch_with_retry(self, index: int) -> tuple[bytes, str]:
        try:
            return self._fetch(index)
        except ApiError as exc:
            if exc.is_quota_error or exc.is_connection_error:
                raise
            logger.warning("Sentence %s failed (%s), retrying once", index, exc)
            return self._fetch(index)

    def _claim(self, gen: _Generation) -> int | None:
        """Next sentence to download, or None when this fetcher should stop. Waits while the
        look-ahead window (prefetch sentences beyond the one being played) is full."""
        with gen.cond:
            while not gen.stop.is_set() and not gen.halted and gen.next_claim < self._total:
                if gen.next_claim - gen.taken <= self._prefetch:
                    index = gen.next_claim
                    gen.next_claim += 1
                    return index
                gen.cond.wait(_POLL_SECONDS)
            return None

    def _deliver(self, gen: _Generation, index: int, item: tuple) -> None:
        """Store the result of `index` and release every result that is now in order."""
        with gen.cond:
            gen.results[index] = item
            while gen.next_emit in gen.results and not gen.halted:
                ready = gen.results.pop(gen.next_emit)
                gen.next_emit += 1
                gen.items.put(ready)
                if ready[0] == "fatal":
                    gen.halted = True
            if gen.next_emit >= self._total and not gen.halted:
                gen.halted = True
                gen.items.put(("end",))
            gen.cond.notify_all()

    def _fetcher(self, gen: _Generation) -> None:
        while (index := self._claim(gen)) is not None:
            started = time.perf_counter()
            try:
                data, ext = self._fetch_with_retry(index)
            except ApiError as exc:
                if exc.is_quota_error or exc.is_connection_error:
                    self._deliver(gen, index, ("fatal", index, exc.message))
                else:
                    self._deliver(gen, index, ("skip", index, exc.message))
                continue
            except Exception as exc:  # never let a fetcher die silently
                logger.exception("Fetcher crashed")
                self._deliver(gen, index, ("fatal", index, str(exc)))
                continue
            self._last_latency_ms = (time.perf_counter() - started) * 1000.0
            self._deliver(gen, index, ("audio", index, data, ext))

    def _consume(self, gen: _Generation) -> None:
        while not gen.stop.is_set():
            try:
                item = gen.items.get(timeout=_POLL_SECONDS)
            except queue.Empty:
                continue
            if item[0] != "end":
                with gen.cond:
                    gen.taken = item[1] + 1
                    gen.cond.notify_all()
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

    def _play_chime(self, gen: _Generation, chime: bytes) -> bool:
        """Play the chapter chime to the end (it can be paused with the rest). False if playback was stopped meanwhile."""
        with self._lock:
            if gen.stop.is_set():
                return False
            try:
                self._output.play(chime, "wav")
            except Exception:  # the chime is a courtesy: never let it stop the story
                logger.warning("Could not play the chapter chime", exc_info=True)
                return True
        while self._output.is_busy() and not gen.stop.is_set():
            time.sleep(_POLL_SECONDS)
        return not gen.stop.is_set()

    def _play(self, gen: _Generation, index: int, data: bytes, ext: str) -> bool:
        chime = self._before_sentence(index) if self._before_sentence else None
        if chime and not self._play_chime(gen, chime):
            return False
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
            self._sentence_length, self._sentence_started = length, time.monotonic()
            self._paused_total, self._pause_started = 0.0, None
        self._callbacks.on_start(index)
        while self._output.is_busy() and not gen.stop.is_set():
            time.sleep(_POLL_SECONDS)
        if gen.stop.is_set():
            return False
        self._callbacks.on_end(index, length)
        stop_after = self.stop_after
        if stop_after is not None and index >= stop_after:
            self._finish(gen)
            self._callbacks.on_stop_point(index)
            return False
        return True

    def _finish(self, gen: _Generation) -> None:
        with self._lock:
            gen.stop.set()
            if self._gen is gen:
                self._gen = None
                self._paused = False
