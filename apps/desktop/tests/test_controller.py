"""ReaderController: bookmark, session reporting and transport logic with a fake API."""

from __future__ import annotations

from typing import Any

from api_client import ApiError
from conftest import FakeOutput, wait_for
from player.controller import ReaderController


class FakeApi:
    def __init__(self, sentences: int = 4, bookmark_index: int = 0, fail_audio: ApiError | None = None):
        self.sentences = [
            {"sentence_index": i, "chapter_index": 1, "text_content": f"Câu {i}.", "word_count": 2}
            for i in range(sentences)
        ]
        self.bookmark_index = bookmark_index
        self.fail_audio = fail_audio
        self.bookmarks: list[tuple] = []
        self.sessions: list[dict[str, Any]] = []
        self.audio_requests: list[tuple] = []

    def get_sentences(self, book_id: int) -> list[dict[str, Any]]:
        return self.sentences

    def get_bookmark(self, book_id: int) -> dict[str, Any]:
        return {"current_sentence_index": self.bookmark_index}

    def save_bookmark(self, book_id: int, chapter: int, index: int, percent: float) -> None:
        self.bookmarks.append((book_id, chapter, index, percent))

    def record_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.sessions.append(payload)
        return {}

    def fetch_audio(self, book_id: int, index: int, speed: float, voice: str | None) -> tuple[bytes, str]:
        self.audio_requests.append((index, speed, voice))
        if self.fail_audio:
            raise self.fail_audio
        return b"x", "wav"


class FakeListener:
    def __init__(self) -> None:
        self.positions: list[int] = []
        self.states: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def on_position(self, index: int) -> None:
        self.positions.append(index)

    def on_state(self, state: str) -> None:
        self.states.append(state)

    def on_warning(self, message: str) -> None:
        self.warnings.append(message)

    def on_error(self, message: str) -> None:
        self.errors.append(message)


def make(api: FakeApi, output: FakeOutput) -> tuple[ReaderController, FakeListener]:
    listener = FakeListener()
    controller = ReaderController(api, output, listener)  # type: ignore[arg-type]
    controller.load_book(1, "Sách")
    return controller, listener


def test_load_book_restores_bookmark_position(output: FakeOutput) -> None:
    controller, _ = make(FakeApi(sentences=5, bookmark_index=3), output)
    assert controller.index == 3 and controller.total == 5


def test_bookmark_beyond_end_is_clamped(output: FakeOutput) -> None:
    controller, _ = make(FakeApi(sentences=2, bookmark_index=99), output)
    assert controller.index == 1


def test_play_to_end_reports_session_and_bookmark(output: FakeOutput) -> None:
    api = FakeApi(sentences=3)
    controller, listener = make(api, output)
    controller.play()
    assert wait_for(lambda: "finished" in listener.states) and wait_for(lambda: api.sessions)
    session = api.sessions[0]
    assert session["sentences_read"] == 3 and session["words_read"] == 6
    assert session["duration_seconds"] > 0 and session["book_id"] == 1
    assert wait_for(lambda: api.bookmarks and api.bookmarks[-1][2] == 2)
    assert api.bookmarks[-1][3] == 100.0


def test_pause_flushes_progress_then_resume_continues(output: FakeOutput) -> None:
    output.duration = 0.15
    api = FakeApi(sentences=4)
    controller, listener = make(api, output)
    controller.play()
    assert wait_for(lambda: len(output.played) >= 2)
    controller.toggle()
    assert controller.is_paused and listener.states[-1] == "paused"
    assert wait_for(lambda: api.sessions)
    controller.toggle()
    assert listener.states[-1] == "playing"
    controller.stop()


def test_jump_while_stopped_moves_without_playing(output: FakeOutput) -> None:
    api = FakeApi(sentences=5)
    controller, listener = make(api, output)
    controller.jump(3)
    assert controller.index == 3 and listener.positions == [3]
    assert output.played == [] and not controller.is_playing
    assert wait_for(lambda: api.bookmarks and api.bookmarks[-1][2] == 3)


def test_jump_is_clamped(output: FakeOutput) -> None:
    controller, _ = make(FakeApi(sentences=3), output)
    controller.jump(-5)
    assert controller.index == 0
    controller.jump(50)
    assert controller.index == 2


def test_jump_while_playing_restarts_from_new_sentence(output: FakeOutput) -> None:
    output.duration = 0.2
    api = FakeApi(sentences=10)
    controller, _ = make(api, output)
    controller.play()
    assert wait_for(lambda: output.played)
    controller.jump(7)
    assert wait_for(lambda: any(r[0] == 7 for r in api.audio_requests))
    controller.stop()


def test_speed_change_restarts_and_requests_new_speed(output: FakeOutput) -> None:
    output.duration = 0.2
    api = FakeApi(sentences=6)
    controller, _ = make(api, output)
    controller.play()
    assert wait_for(lambda: output.played)
    controller.set_speed(1.5)
    assert wait_for(lambda: any(r[1] == 1.5 for r in api.audio_requests))
    controller.stop()


def test_voice_is_sent_to_backend(output: FakeOutput) -> None:
    api = FakeApi(sentences=1)
    controller, listener = make(api, output)
    controller.voice = "mock-vi-male"
    controller.play()
    assert wait_for(lambda: "finished" in listener.states)
    assert api.audio_requests[0] == (0, 1.0, "mock-vi-male")


def test_quota_error_stops_and_reports(output: FakeOutput) -> None:
    api = FakeApi(sentences=3, fail_audio=ApiError(429, "Daily character limit reached."))
    controller, listener = make(api, output)
    controller.play()
    assert wait_for(lambda: listener.errors)
    assert "limit" in listener.errors[0] and listener.states[-1] == "stopped"
    assert api.sessions == []  # nothing was read, nothing reported


def test_skipped_sentence_raises_warning(output: FakeOutput) -> None:
    api = FakeApi(sentences=2, fail_audio=ApiError(500, "tts down"))
    controller, listener = make(api, output)
    controller.play()
    assert wait_for(lambda: "finished" in listener.states)
    assert len(listener.warnings) == 2 and "Bỏ qua câu 1" in listener.warnings[0]


def test_close_book_flushes_synchronously(output: FakeOutput) -> None:
    output.duration = 0.05
    api = FakeApi(sentences=6)
    controller, _ = make(api, output)
    controller.play()
    assert wait_for(lambda: len(output.played) >= 2)
    controller.close_book()
    assert api.sessions and api.bookmarks  # written before close_book returned
    assert controller.book is None and not controller.is_playing


def test_open_second_book_saves_first_books_bookmark(output: FakeOutput) -> None:
    api = FakeApi(sentences=4, bookmark_index=2)
    controller, _ = make(api, output)
    controller.load_book(2, "Sách 2")
    assert api.bookmarks and api.bookmarks[-1][0] == 1  # first book saved at index 2
    assert controller.book and controller.book.book_id == 2
