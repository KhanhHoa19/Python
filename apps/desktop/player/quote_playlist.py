"""Plays the saved audio of a list of quotes one after another ("Phát liên tục"). No Tk; testable with a fake output."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from player.audio_output import AudioOutput

logger = logging.getLogger(__name__)

FetchQuoteAudio = Callable[[int], tuple[bytes, str]]


@dataclass
class _Run:
    ids: Sequence[int]
    start: int
    stop: threading.Event = field(default_factory=threading.Event)
    jump: int | None = None


class QuotePlaylist:
    """`on_change(position)` is called from the worker thread with the index being played, and with None when the
    playlist ended or was stopped. A quote whose audio cannot be loaded is reported (`on_error`) and skipped."""

    def __init__(self, fetch: FetchQuoteAudio, output: AudioOutput, on_change: Callable[[int | None], None],
                 on_error: Callable[[str], None] = lambda message: None, poll_seconds: float = 0.05):
        self._fetch, self._output, self._on_change, self._on_error = fetch, output, on_change, on_error
        self._poll = poll_seconds
        self._run: _Run | None = None
        self._position: int | None = None
        self._lock = threading.Lock()

    @property
    def playing(self) -> bool:
        return self._run is not None and not self._run.stop.is_set()

    @property
    def position(self) -> int | None:
        return self._position if self.playing else None

    def start(self, ids: Sequence[int], from_index: int = 0) -> None:
        """Replace whatever is playing with this list, beginning at `from_index`."""
        self.stop(notify=False)
        if not ids:
            return
        run = _Run(ids=list(ids), start=min(max(from_index, 0), len(ids) - 1))
        with self._lock:
            self._run = run
        threading.Thread(target=self._work, args=(run,), daemon=True, name="quote-playlist").start()

    def stop(self, notify: bool = True) -> None:
        with self._lock:
            run, self._run, self._position = self._run, None, None
        if run is not None:
            run.stop.set()
            self._output.stop()
            if notify:
                self._on_change(None)

    def step(self, direction: int) -> None:
        """Skip to the next (+1) or previous (-1) quote; past either end the playlist stops."""
        run = self._run
        if run is None or self._position is None:
            return
        target = self._position + direction
        if 0 <= target < len(run.ids):
            run.jump = target
        else:
            self.stop()

    def _work(self, run: _Run) -> None:
        position = run.start
        while not run.stop.is_set() and 0 <= position < len(run.ids):
            self._position = position
            self._on_change(position)
            try:
                data, ext = self._fetch(run.ids[position])
                if run.stop.is_set():
                    return
                self._output.play(data, ext)
            except Exception as exc:  # noqa: BLE001  (one bad file, whatever it is, must not end the playlist)
                logger.warning("Quote %s could not be played: %s", run.ids[position], exc)
                self._on_error(str(getattr(exc, "message", exc)))
                position += 1
                continue
            while self._output.is_busy() and not run.stop.is_set() and run.jump is None:
                time.sleep(self._poll)
            if run.stop.is_set():
                return
            if run.jump is not None:
                position, run.jump = run.jump, None
                self._output.stop()
                continue
            position += 1
        if not run.stop.is_set():
            with self._lock:
                if self._run is run:
                    self._run, self._position = None, None
            self._on_change(None)
