"""Reader controller: owns the open book, the playback engine, bookmark and session reporting.

No Tk code here. The UI implements `ReaderListener` and receives events from worker threads,
so it must forward them to the main thread (see ui/dispatcher.py).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

import config
from api_client import ApiClient, ApiError
from player.ambient import AmbientPlayer
from player.audio_output import AudioOutput
from player.chime import make_chime_wav
from player.engine import EngineCallbacks, PlaybackEngine
from player.sleep_timer import FADE_SECONDS, SleepTimer, chapter_end, fade_volume

logger = logging.getLogger(__name__)


class ReaderListener(Protocol):
    def on_position(self, index: int) -> None: ...
    def on_state(self, state: str) -> None: ...  # "playing" | "paused" | "stopped" | "finished"
    def on_warning(self, message: str) -> None: ...
    def on_error(self, message: str) -> None: ...


@dataclass
class OpenBook:
    book_id: int
    title: str
    sentences: list[dict[str, Any]]
    chapters: list[dict[str, Any]] = field(default_factory=list)  # table of contents; empty if unavailable


class ReaderController:
    def __init__(self, api: ApiClient, output: AudioOutput, listener: ReaderListener):
        self.api = api
        self.output = output
        self.listener = listener
        self.book: OpenBook | None = None
        self.index = 0
        self.voice: str | None = None
        self.saved_voice: str | None = None  # voice remembered in the open book's bookmark
        self.speed = 1.0
        self.prefetch = 2
        self.fetch_workers = 2  # benchmark: one downloader stalls 45% at 1.5x when TTS takes 3 s
        self._engine: PlaybackEngine | None = None
        self._session_started: datetime | None = None
        self._session_seconds = 0.0
        self._session_sentences = 0
        self._session_words = 0
        self._last_bookmark_save = 0.0
        self.sleep = SleepTimer()
        self.ambient = AmbientPlayer(output, fetch=lambda track_id: api.fetch_ambient(track_id))
        self.chapter_chime = True
        self._chime: bytes | None = None
        self._last_started: int | None = None  # the sentence that started last: a chime only marks a continuous move
        self._volume = 1.0
        self._lock = threading.Lock()

    # -- state -------------------------------------------------------------------------

    @property
    def total(self) -> int:
        return len(self.book.sentences) if self.book else 0

    @property
    def is_playing(self) -> bool:
        return bool(self._engine and self._engine.is_running and not self._engine.is_paused)

    @property
    def is_paused(self) -> bool:
        return bool(self._engine and self._engine.is_paused)

    @property
    def engine_status(self) -> tuple[int, int, float]:
        """(buffered, prefetch, last latency ms) for the status line."""
        if not self._engine:
            return 0, self.prefetch, 0.0
        return self._engine.buffered, self._engine.prefetch, self._engine.last_latency_ms

    # -- opening ---------------------------------------------------------------------------

    def load_book(self, book_id: int, title: str) -> int:
        """Blocking: fetch sentences + bookmark, replace the open book. Returns the start index."""
        sentences = self.api.get_sentences(book_id)
        bookmark = self.api.get_bookmark(book_id)
        self.close_book()
        try:
            chapters = self.api.get_chapters(book_id)
        except ApiError:  # no table of contents is not a reason to refuse reading
            chapters = []
        self.book = OpenBook(book_id, title, sentences, chapters)
        self.saved_voice = bookmark.get("voice") or None
        start = int(bookmark.get("current_sentence_index", 0))
        self.index = min(max(start, 0), max(len(sentences) - 1, 0))
        return self.index

    def close_book(self) -> None:
        """Stop playback and flush bookmark + session for the current book."""
        self._stop_engine()
        self.sleep_cancel()  # a timer never carries over to another book
        self._flush_session(blocking=True)
        self._save_bookmark(blocking=True)
        self.book = None
        self.index = 0

    # -- transport ---------------------------------------------------------------------------

    def play(self, index: int | None = None) -> None:
        if not self.book or not self.total:
            return
        if index is not None:
            self.index = min(max(index, 0), self.total - 1)
        self._stop_engine()
        self._last_started = None
        self._ensure_session()
        # Announce "playing" BEFORE starting threads: a fast failure would otherwise report
        # "stopped" first and this call would then overwrite it with a stale "playing".
        self._announce("playing")
        self._engine = PlaybackEngine(
            fetch=self._fetch, output=self.output, total=self.total,
            callbacks=EngineCallbacks(
                on_start=self._on_start, on_end=self._on_end, on_skip=self._on_skip,
                on_finished=self._on_finished, on_fatal=self._on_fatal, on_stop_point=self._on_stop_point,
            ),
            prefetch=self.prefetch, fetch_workers=self.fetch_workers, before_sentence=self._chime_before,
        )
        self._engine.stop_after = self._stop_point(self.index)
        self._engine.start(self.index)

    def toggle(self) -> None:
        if self.is_playing and self._engine:
            self._engine.pause()
            self._flush_session(blocking=False)
            self._save_bookmark(blocking=False)
            self._announce("paused")
        elif self.is_paused and self._engine:
            self._engine.resume()
            self._ensure_session()
            self._announce("playing")
        else:
            self.play()

    def stop(self) -> None:
        self._stop_engine()
        self._flush_session(blocking=False)
        self._save_bookmark(blocking=False)
        self._announce("stopped")

    def jump(self, index: int, autoplay: bool | None = None) -> None:
        """Move to a sentence. Keeps playing if it was playing (or if autoplay is True)."""
        if not self.book or not self.total:
            return
        self.index = min(max(index, 0), self.total - 1)
        self.listener.on_position(self.index)
        should_play = self.is_playing or self.is_paused if autoplay is None else autoplay
        if should_play:
            self.play(self.index)
        else:
            self._save_bookmark(blocking=False)

    def next(self) -> None:
        self.jump(self.index + 1)

    def previous(self) -> None:
        self.jump(self.index - 1)

    def set_speed(self, speed: float) -> None:
        if speed == self.speed:
            return
        self.speed = speed
        if self.is_playing or self.is_paused:
            self.play(self.index)  # prefetched audio has the old speed

    def set_voice(self, voice: str | None) -> None:
        if voice == self.voice:
            return
        self._flush_session(blocking=False)  # a session belongs to one voice
        self.voice = voice
        if self.is_playing or self.is_paused:
            self.play(self.index)

    # -- sleep timer ---------------------------------------------------------------------------

    def _stop_point(self, index: int) -> int | None:
        """Last sentence to play before stopping, when the timer is in "end of chapter" mode."""
        if self.sleep.mode != "chapter" or not self.book:
            return None
        return chapter_end(self.book.sentences, index)

    def _set_volume(self, volume: float) -> None:
        if volume != self._volume:
            self._volume = volume
            self.output.set_volume(volume)
            self.ambient.set_fade(volume)  # the sleep timer's fade-out lowers the background too

    def _announce(self, state: str) -> None:
        """Tell the UI the state changed; the background sound plays only while the reader does."""
        self.ambient.set_playing(state == "playing")
        self.listener.on_state(state)

    def _chime_before(self, index: int) -> bytes | None:
        """The chapter chime, when playback moves on by itself into the first sentence of a new chapter."""
        book = self.book
        if not self.chapter_chime or not book or index <= 0 or self._last_started != index - 1 or index >= len(book.sentences):
            return None
        if book.sentences[index].get("chapter_index") == book.sentences[index - 1].get("chapter_index"):
            return None
        if self._chime is None:
            self._chime = make_chime_wav()
        return self._chime

    def sleep_minutes(self, minutes: int) -> None:
        self.sleep.start_minutes(minutes)
        self._set_volume(1.0)
        if self._engine:
            self._engine.stop_after = None

    def sleep_chapter(self) -> None:
        self.sleep.start_chapter()
        self._set_volume(1.0)
        if self._engine:
            self._engine.stop_after = self._stop_point(self.index)

    def sleep_cancel(self) -> None:
        self.sleep.cancel()
        self._set_volume(1.0)
        if self._engine:
            self._engine.stop_after = None

    def sleep_tick(self) -> str:
        """Call about 5 times a second from the UI thread. Fades, pauses when time is up, returns the button text."""
        timer = self.sleep
        if not timer.active:
            return timer.label()
        playing = self.is_playing
        remaining = timer.tick(playing)
        if timer.mode == "minutes":
            self._set_volume(fade_volume(remaining))
            if remaining <= 0:
                if playing:
                    self.toggle()  # pause + save the position
                self.sleep_cancel()  # restores the volume for the next listen
                self.listener.on_warning("Hết giờ hẹn: đã tạm dừng.")
        elif playing and self._engine and self.book and self.index == chapter_end(self.book.sentences, self.index):
            length = self._engine.sentence_length
            self._set_volume(fade_volume(self._engine.sentence_remaining(), min(FADE_SECONDS, length)))
        else:
            self._set_volume(1.0)
        return timer.label()

    # -- engine callbacks (worker threads) ----------------------------------------------------

    def _fetch(self, index: int) -> tuple[bytes, str]:
        assert self.book is not None
        return self.api.fetch_audio(self.book.book_id, index, self.speed, self.voice)

    def _on_start(self, index: int) -> None:
        self.index = index
        self._last_started = index
        if self._engine:
            self._engine.stop_after = self._stop_point(index)
        self.listener.on_position(index)
        now = time.monotonic()
        if now - self._last_bookmark_save >= config.BOOKMARK_SAVE_INTERVAL_SECONDS:
            self._last_bookmark_save = now
            self._save_bookmark(blocking=False)

    def _on_end(self, index: int, seconds: float) -> None:
        with self._lock:
            self._session_seconds += seconds
            self._session_sentences += 1
            if self.book and 0 <= index < self.total:
                self._session_words += int(self.book.sentences[index].get("word_count", 0))

    def _on_skip(self, index: int, message: str) -> None:
        self.listener.on_warning(f"Bỏ qua câu {index + 1} (lỗi TTS: {message})")

    def _on_finished(self) -> None:
        self._flush_session(blocking=False)
        self._save_bookmark(blocking=False)
        self._announce("finished")

    def _on_stop_point(self, index: int) -> None:
        """The sleep timer's chapter ended: stop on the first sentence of the next chapter, ready to resume."""
        self.sleep.cancel()
        self._set_volume(1.0)
        if index + 1 >= self.total:
            self._on_finished()
            return
        self.index = index + 1
        self._flush_session(blocking=False)
        self._save_bookmark(blocking=False)
        self.listener.on_position(self.index)
        self._announce("stopped")
        self.listener.on_warning("Đã dừng hết chương theo hẹn giờ.")

    def _on_fatal(self, message: str) -> None:
        self._flush_session(blocking=False)
        self._save_bookmark(blocking=False)
        self._announce("stopped")
        self.listener.on_error(message)

    # -- bookmark / session reporting ------------------------------------------------------------

    def _stop_engine(self) -> None:
        if self._engine:
            self._engine.stop()
            self._engine = None

    def _ensure_session(self) -> None:
        with self._lock:
            if self._session_started is None:
                self._session_started = datetime.now(UTC)

    def _flush_session(self, blocking: bool) -> None:
        with self._lock:
            started, seconds = self._session_started, self._session_seconds
            sentences, words = self._session_sentences, self._session_words
            self._session_started, self._session_seconds = None, 0.0
            self._session_sentences = self._session_words = 0
            voice = self.voice
        if started is None or sentences == 0 or not self.book:
            return
        payload = {
            "book_id": self.book.book_id,
            "start_time": started.isoformat(),
            "end_time": datetime.now(UTC).isoformat(),
            "duration_seconds": round(seconds, 1),
            "sentences_read": sentences,
            "words_read": words,
        }
        if voice:
            payload["voice"] = voice
        self._run(lambda: self.api.record_session(payload), blocking)

    def _save_bookmark(self, blocking: bool) -> None:
        if not self.book or not self.total:
            return
        book_id, index = self.book.book_id, min(self.index, self.total - 1)
        chapter = int(self.book.sentences[index].get("chapter_index", 1))
        percent = round((index + 1) / self.total * 100.0, 1)
        voice = self.voice
        self._run(lambda: self.api.save_bookmark(book_id, chapter, index, percent, voice), blocking)

    def _run(self, job: Any, blocking: bool) -> None:
        def safe() -> None:
            try:
                job()
            except ApiError as exc:
                logger.warning("Background save failed: %s", exc.message)

        if blocking:
            safe()
        else:
            threading.Thread(target=safe, daemon=True).start()
