"""Sleep timer: pure rules, engine stop point, and the controller's countdown / fade / stop."""

from __future__ import annotations

import threading
import time

import pytest
from conftest import FakeOutput, wait_for
from test_controller import FakeApi, FakeListener

from player.controller import ReaderController
from player.engine import EngineCallbacks, PlaybackEngine
from player.sleep_timer import (
    SleepTimer,
    chapter_end,
    fade_volume,
    format_remaining,
    is_last_of_chapter,
    parse_custom_minutes,
)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


# ---------------------------------------------------------------- pure rules

def test_fade_is_full_then_linear_then_zero() -> None:
    assert fade_volume(600) == 1 and fade_volume(10) == 1
    assert fade_volume(5) == pytest.approx(0.5) and fade_volume(1) == pytest.approx(0.1)
    assert fade_volume(0) == 0 and fade_volume(-2) == 0
    assert fade_volume(2, 4) == pytest.approx(0.5) and fade_volume(1, 0) == 0


def test_format_remaining_rounds_up() -> None:
    assert format_remaining(750) == "12:30" and format_remaining(0.2) == "00:01"
    assert format_remaining(0) == "00:00" and format_remaining(-4) == "00:00"


def test_chapter_helpers() -> None:
    sentences = [{"chapter_index": c} for c in (1, 1, 2, 2, 2, 3)]
    assert [is_last_of_chapter(sentences, i) for i in range(6)] == [False, True, False, False, True, True]
    assert [chapter_end(sentences, i) for i in range(6)] == [1, 1, 4, 4, 4, 5]


def test_parse_custom_minutes() -> None:
    assert parse_custom_minutes("25") == 25 and parse_custom_minutes(" 600 ") == 600
    for bad in ("", "0", "601", "-5", "1.5", "abc", "12 phút", "٣"):
        assert parse_custom_minutes(bad) is None


def test_timer_counts_down_only_while_playing() -> None:
    clock = Clock()
    timer = SleepTimer(clock)
    timer.start_minutes(15)
    clock.now += 60
    assert timer.tick(playing=True) == 840
    clock.now += 120
    assert timer.tick(playing=False) == 840  # paused: the clock does not run
    clock.now += 30
    assert timer.tick(playing=True) == 810
    assert timer.label() == "13:30"
    clock.now += 10_000
    assert timer.tick(playing=True) == 0
    timer.cancel()
    assert not timer.active and timer.label() == "Hẹn giờ"


def test_timer_labels() -> None:
    timer = SleepTimer(Clock())
    assert timer.label() == "Hẹn giờ"
    timer.start_chapter()
    assert timer.active and timer.label() == "Hết chương"


# ---------------------------------------------------------------- engine

def test_engine_stops_after_the_requested_sentence(output: FakeOutput) -> None:
    stopped: list[int] = []
    finished = threading.Event()
    started: list[int] = []
    callbacks = EngineCallbacks(on_start=started.append, on_stop_point=stopped.append, on_finished=finished.set)
    engine = PlaybackEngine(lambda i: (b"x", "wav"), output, total=10, callbacks=callbacks)
    engine.stop_after = 3
    engine.start(0)
    assert wait_for(lambda: stopped == [3])
    assert started == [0, 1, 2, 3] and not finished.is_set() and not engine.is_running


def test_engine_reports_sentence_remaining_without_paused_time(output: FakeOutput) -> None:
    output.duration = 5.0
    engine = PlaybackEngine(lambda i: (b"x", "wav"), output, total=3, callbacks=EngineCallbacks())
    engine.start(0)
    assert wait_for(lambda: engine.sentence_length == 5.0)
    first = engine.sentence_remaining()
    assert 4.0 < first <= 5.0
    engine.stop()


# ---------------------------------------------------------------- controller

def make(api: FakeApi, output: FakeOutput, clock: Clock) -> tuple[ReaderController, FakeListener]:
    listener = FakeListener()
    controller = ReaderController(api, output, listener)  # type: ignore[arg-type]
    controller.sleep = SleepTimer(clock)
    controller.load_book(1, "Sách")
    return controller, listener


def test_countdown_fades_then_pauses_and_restores_volume(output: FakeOutput) -> None:
    clock = Clock()
    output.duration = 30.0  # one long sound, so nothing else changes the state
    controller, listener = make(FakeApi(sentences=3), output, clock)
    controller.sleep_minutes(1)
    controller.play()
    assert wait_for(lambda: len(output.played) == 1)

    clock.now += 30
    assert controller.sleep_tick() == "00:30" and output.volume == 1.0  # before the last 10 seconds
    clock.now += 25  # 5 s left
    assert controller.sleep_tick() == "00:05"
    assert output.volume == pytest.approx(0.5)
    clock.now += 4  # 1 s left
    controller.sleep_tick()
    assert output.volume == pytest.approx(0.1)
    clock.now += 2  # time is up
    assert controller.sleep_tick() == "Hẹn giờ"
    assert "paused" in listener.states and not controller.is_playing
    assert output.volume == 1.0 and not controller.sleep.active
    assert any("Hết giờ hẹn" in w for w in listener.warnings)


def test_paused_player_keeps_its_remaining_time(output: FakeOutput) -> None:
    clock = Clock()
    output.duration = 30.0
    controller, _ = make(FakeApi(sentences=2), output, clock)
    controller.sleep_minutes(15)
    controller.play()
    assert wait_for(lambda: len(output.played) == 1)
    clock.now += 60
    controller.sleep_tick()
    controller.toggle()  # pause
    clock.now += 600
    assert controller.sleep_tick() == "14:00"


def test_chapter_mode_stops_on_the_first_sentence_of_the_next_chapter(output: FakeOutput) -> None:
    api = FakeApi(sentences=6)
    for sentence, chapter in zip(api.sentences, (1, 1, 1, 2, 2, 2), strict=True):
        sentence["chapter_index"] = chapter
    controller, listener = make(api, output, Clock())
    controller.sleep_chapter()
    controller.play()
    assert wait_for(lambda: "stopped" in listener.states)
    assert output.played and len(output.played) == 3  # sentences 0-2 played, nothing of chapter 2
    assert controller.index == 3 and not controller.sleep.active
    assert any("hết chương" in w for w in listener.warnings)
    assert wait_for(lambda: api.bookmarks and api.bookmarks[-1][2] == 3)  # resumes at the next chapter
    assert output.volume == 1.0


def test_chapter_mode_at_the_end_of_the_book_finishes(output: FakeOutput) -> None:
    controller, listener = make(FakeApi(sentences=2), output, Clock())
    controller.sleep_chapter()
    controller.play()
    assert wait_for(lambda: "finished" in listener.states)
    assert not controller.sleep.active


def test_chapter_fade_runs_over_the_last_sentence_only(output: FakeOutput) -> None:
    api = FakeApi(sentences=4)
    for sentence, chapter in zip(api.sentences, (1, 1, 2, 2), strict=True):
        sentence["chapter_index"] = chapter
    output.duration = 1.0
    controller, _ = make(api, output, Clock())
    controller.sleep_chapter()
    controller.play(0)
    assert wait_for(lambda: len(output.played) == 1)
    controller.sleep_tick()
    assert output.volume == 1.0  # sentence 0 is not the last of chapter 1

    assert wait_for(lambda: len(output.played) == 2)  # sentence 1 ends the chapter: it fades over its length
    time.sleep(0.5)
    controller.sleep_tick()
    assert 0.05 < output.volume < 0.95
    controller.close_book()
    assert controller.sleep.active is False and output.volume == 1.0  # a timer never carries over


def test_cancel_restores_volume_and_stop_point(output: FakeOutput) -> None:
    controller, _ = make(FakeApi(sentences=3), output, Clock())
    controller.sleep_minutes(1)
    controller._set_volume(0.3)
    controller.sleep_cancel()
    assert output.volume == 1.0 and not controller.sleep.active
