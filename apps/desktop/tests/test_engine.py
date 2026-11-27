"""Producer-consumer engine behaviour."""

from __future__ import annotations

import threading
import time

from api_client import ApiError
from conftest import FakeOutput, wait_for
from player.engine import EngineCallbacks, PlaybackEngine


class Recorder:
    def __init__(self) -> None:
        self.started: list[int] = []
        self.ended: list[int] = []
        self.skipped: list[tuple[int, str]] = []
        self.finished = threading.Event()
        self.fatal: list[str] = []

    def callbacks(self) -> EngineCallbacks:
        return EngineCallbacks(
            on_start=self.started.append,
            on_end=lambda i, s: self.ended.append(i),
            on_skip=lambda i, m: self.skipped.append((i, m)),
            on_finished=self.finished.set,
            on_fatal=self.fatal.append,
        )


def fetch_ok(index: int) -> tuple[bytes, str]:
    return f"audio-{index}".encode(), "wav"


def test_plays_all_sentences_in_order(output: FakeOutput) -> None:
    rec = Recorder()
    engine = PlaybackEngine(fetch_ok, output, total=4, callbacks=rec.callbacks())
    engine.start(0)
    assert rec.finished.wait(3)
    assert rec.started == [0, 1, 2, 3] and rec.ended == [0, 1, 2, 3]
    assert output.played == [b"audio-0", b"audio-1", b"audio-2", b"audio-3"]
    assert not engine.is_running


def test_start_from_middle(output: FakeOutput) -> None:
    rec = Recorder()
    engine = PlaybackEngine(fetch_ok, output, total=5, callbacks=rec.callbacks())
    engine.start(3)
    assert rec.finished.wait(3)
    assert rec.started == [3, 4]


def test_prefetch_queue_is_bounded(output: FakeOutput) -> None:
    fetched: list[int] = []
    output.duration = 5.0  # first sentence plays "forever"

    def fetch(index: int) -> tuple[bytes, str]:
        fetched.append(index)
        return b"x", "wav"

    engine = PlaybackEngine(fetch, output, total=50, callbacks=Recorder().callbacks(), prefetch=2)
    engine.start(0)
    assert wait_for(lambda: len(output.played) == 1)
    time.sleep(0.2)
    # 1 playing + 2 queued + 1 blocked waiting for room = at most 4 fetched
    assert len(fetched) <= 4
    engine.stop()


def test_failed_sentence_is_retried_once_then_skipped(output: FakeOutput) -> None:
    attempts: dict[int, int] = {}

    def fetch(index: int) -> tuple[bytes, str]:
        attempts[index] = attempts.get(index, 0) + 1
        if index == 1:
            raise ApiError(500, "boom")
        return b"x", "wav"

    rec = Recorder()
    PlaybackEngine(fetch, output, total=3, callbacks=rec.callbacks()).start(0)
    assert rec.finished.wait(3)
    assert attempts[1] == 2
    assert rec.skipped == [(1, "boom")]
    assert rec.started == [0, 2]


def test_retry_succeeds_on_second_attempt(output: FakeOutput) -> None:
    attempts = {"n": 0}

    def fetch(index: int) -> tuple[bytes, str]:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise ApiError(500, "flaky")
        return b"x", "wav"

    rec = Recorder()
    PlaybackEngine(fetch, output, total=1, callbacks=rec.callbacks()).start(0)
    assert rec.finished.wait(3) and rec.skipped == []


def test_quota_error_is_fatal_and_not_retried(output: FakeOutput) -> None:
    calls = {"n": 0}

    def fetch(index: int) -> tuple[bytes, str]:
        calls["n"] += 1
        raise ApiError(429, "Daily character limit reached.")

    rec = Recorder()
    engine = PlaybackEngine(fetch, output, total=3, callbacks=rec.callbacks())
    engine.start(0)
    assert wait_for(lambda: rec.fatal)
    assert rec.fatal == ["Daily character limit reached."] and calls["n"] == 1
    assert not rec.finished.is_set() and not engine.is_running


def test_connection_error_is_fatal(output: FakeOutput) -> None:
    def fetch(index: int) -> tuple[bytes, str]:
        raise ApiError(0, "Không kết nối được máy chủ.")

    rec = Recorder()
    PlaybackEngine(fetch, output, total=2, callbacks=rec.callbacks()).start(0)
    assert wait_for(lambda: rec.fatal)


def test_stop_halts_playback_and_silences_output(output: FakeOutput) -> None:
    output.duration = 0.2
    rec = Recorder()
    engine = PlaybackEngine(fetch_ok, output, total=20, callbacks=rec.callbacks())
    engine.start(0)
    assert wait_for(lambda: rec.started)
    engine.stop()
    played_at_stop = len(output.played)
    time.sleep(0.4)
    assert len(output.played) == played_at_stop and output.stops >= 1
    assert not rec.finished.is_set()


def test_restart_discards_old_generation(output: FakeOutput) -> None:
    gate = threading.Event()

    def slow_then_ok(index: int) -> tuple[bytes, str]:
        if index == 0:
            gate.wait(2)  # old producer stuck in a slow request
        return f"a{index}".encode(), "wav"

    rec = Recorder()
    engine = PlaybackEngine(slow_then_ok, output, total=3, callbacks=rec.callbacks())
    engine.start(0)
    time.sleep(0.05)
    engine.start(1)  # jump while the first request is still pending
    assert wait_for(rec.finished.is_set)
    gate.set()
    time.sleep(0.2)
    assert rec.started == [1, 2]  # stale sentence 0 never played
    assert b"a0" not in output.played


def test_pause_and_resume(output: FakeOutput) -> None:
    output.duration = 0.1
    rec = Recorder()
    engine = PlaybackEngine(fetch_ok, output, total=3, callbacks=rec.callbacks())
    engine.start(0)
    assert wait_for(lambda: rec.started)
    engine.pause()
    assert engine.is_paused
    time.sleep(0.3)
    assert len(rec.ended) == 0  # nothing advances while paused
    engine.resume()
    assert rec.finished.wait(3)


def test_parallel_fetch_keeps_sentence_order(output: FakeOutput) -> None:
    def fetch(index: int) -> tuple[bytes, str]:
        time.sleep(0.15 if index % 2 == 0 else 0.01)  # even sentences finish AFTER the odd ones
        return f"audio-{index}".encode(), "wav"

    rec = Recorder()
    engine = PlaybackEngine(fetch, output, total=8, callbacks=rec.callbacks(), prefetch=4, fetch_workers=3)
    engine.start(0)
    assert rec.finished.wait(5)
    assert rec.started == list(range(8))
    assert output.played == [f"audio-{i}".encode() for i in range(8)]


def test_parallel_fetch_stays_within_look_ahead_window(output: FakeOutput) -> None:
    fetched: list[int] = []
    output.duration = 5.0

    def fetch(index: int) -> tuple[bytes, str]:
        fetched.append(index)
        return b"x", "wav"

    engine = PlaybackEngine(fetch, output, total=50, callbacks=Recorder().callbacks(), prefetch=3, fetch_workers=4)
    engine.start(0)
    assert wait_for(lambda: len(output.played) == 1)
    time.sleep(0.2)
    assert len(fetched) <= 5  # playing sentence + prefetch 3 + the one being awaited
    engine.stop()


def test_parallel_fetch_skips_and_fatal_arrive_in_order(output: FakeOutput) -> None:
    def fetch(index: int) -> tuple[bytes, str]:
        if index == 1:
            time.sleep(0.1)
            raise ApiError(502, "boom")
        if index == 3:
            raise ApiError(429, "quota")
        return b"x", "wav"

    rec = Recorder()
    engine = PlaybackEngine(fetch, output, total=6, callbacks=rec.callbacks(), prefetch=4, fetch_workers=3)
    engine.start(0)
    assert wait_for(lambda: rec.fatal)
    assert rec.started == [0, 2] and [i for i, _ in rec.skipped] == [1]
    assert not rec.finished.is_set()
