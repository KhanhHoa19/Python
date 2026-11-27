"""Sleep timer rules (same as apps/web/src/lib/sleepTimer.ts). No Tk, no audio: easy to test."""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Sequence
from typing import Any

FADE_SECONDS = 10.0
CUSTOM_MINUTES_MAX = 600
MINUTE_PRESETS = (15, 30, 45, 60)


def fade_volume(remaining: float, window: float = FADE_SECONDS) -> float:
    """Volume (0-1): full until the last `window` seconds, then a straight line down to 0."""
    if window <= 0 or remaining <= 0:
        return 0.0
    if remaining >= window:
        return 1.0
    return remaining / window


def format_remaining(seconds: float) -> str:
    """'12:30' for 750 s; rounds up so '00:00' is only shown when time is really up."""
    total = max(0, math.ceil(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def is_last_of_chapter(sentences: Sequence[dict[str, Any]], index: int) -> bool:
    """True when sentence `index` is the last of its chapter (or of the book)."""
    if index + 1 >= len(sentences):
        return True
    return sentences[index + 1].get("chapter_index") != sentences[index].get("chapter_index")


def chapter_end(sentences: Sequence[dict[str, Any]], index: int) -> int:
    """Index of the last sentence of the chapter that contains `index`."""
    while not is_last_of_chapter(sentences, index):
        index += 1
    return index


def parse_custom_minutes(text: str) -> int | None:
    """Whole minutes from a text field, or None unless it is a number from 1 to CUSTOM_MINUTES_MAX."""
    text = text.strip()
    if not text.isascii() or not text.isdigit():
        return None
    value = int(text)
    return value if 1 <= value <= CUSTOM_MINUTES_MAX else None


class SleepTimer:
    """Either a countdown in minutes (runs only while playing) or 'stop at the end of this chapter'."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self.mode: str | None = None  # "minutes" | "chapter" | None
        self.minutes = 0
        self.remaining = 0.0
        self._last = 0.0

    @property
    def active(self) -> bool:
        return self.mode is not None

    def start_minutes(self, minutes: int) -> None:
        self.mode, self.minutes, self.remaining, self._last = "minutes", minutes, minutes * 60.0, self._clock()

    def start_chapter(self) -> None:
        self.mode, self.minutes, self.remaining, self._last = "chapter", 0, 0.0, self._clock()

    def cancel(self) -> None:
        self.mode, self.minutes, self.remaining = None, 0, 0.0

    def tick(self, playing: bool) -> float:
        """Advance the countdown by the time since the last tick, if playing. Returns seconds left."""
        now = self._clock()
        if self.mode == "minutes" and playing:
            self.remaining = max(0.0, self.remaining - (now - self._last))
        self._last = now
        return self.remaining

    def label(self) -> str:
        """Text of the timer button in the reader."""
        if self.mode == "chapter":
            return "Hết chương"
        if self.mode == "minutes":
            return format_remaining(self.remaining)
        return "Hẹn giờ"
