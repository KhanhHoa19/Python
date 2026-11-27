"""The play-all mode of the quotes screen: order, skipping, stepping, stopping."""

from __future__ import annotations

import threading

from conftest import FakeOutput, wait_for

from api_client import ApiError
from player.quote_playlist import QuotePlaylist


def make(output: FakeOutput, fail: set[int] | None = None):
    changes: list[int | None] = []
    errors: list[str] = []
    fetched: list[int] = []

    def fetch(note_id: int) -> tuple[bytes, str]:
        fetched.append(note_id)
        if note_id in (fail or set()):
            raise ApiError(404, f"no audio for {note_id}")
        return f"audio-{note_id}".encode(), "wav"

    return QuotePlaylist(fetch, output, changes.append, errors.append, poll_seconds=0.005), changes, errors, fetched


def test_plays_every_quote_in_order_then_reports_the_end(output: FakeOutput) -> None:
    playlist, changes, _, _ = make(output)
    playlist.start([10, 20, 30])
    assert wait_for(lambda: changes[-1:] == [None] and len(changes) == 4)
    assert changes == [0, 1, 2, None]
    assert output.played == [b"audio-10", b"audio-20", b"audio-30"]
    assert not playlist.playing and playlist.position is None


def test_starting_in_the_middle(output: FakeOutput) -> None:
    playlist, changes, _, _ = make(output)
    playlist.start([1, 2, 3, 4], from_index=2)
    assert wait_for(lambda: changes[-1:] == [None])
    assert output.played == [b"audio-3", b"audio-4"]
    playlist.start([1, 2], from_index=99)  # clamped to the last quote
    assert wait_for(lambda: output.played[-1:] == [b"audio-2"])


def test_a_quote_without_audio_is_reported_and_skipped(output: FakeOutput) -> None:
    playlist, changes, errors, _ = make(output, fail={2})
    playlist.start([1, 2, 3])
    assert wait_for(lambda: changes[-1:] == [None])
    assert output.played == [b"audio-1", b"audio-3"] and errors == ["no audio for 2"]


def test_stop_silences_at_once_and_notifies(output: FakeOutput) -> None:
    output.duration = 5.0
    playlist, changes, _, _ = make(output)
    playlist.start([1, 2, 3])
    assert wait_for(lambda: len(output.played) == 1)
    assert playlist.playing and playlist.position == 0
    playlist.stop()
    assert changes[-1] is None and not playlist.playing and output.stops >= 1
    assert len(output.played) == 1  # nothing after the stop


def test_next_and_previous_jump_and_the_ends_stop(output: FakeOutput) -> None:
    output.duration = 5.0
    playlist, changes, _, _ = make(output)
    playlist.start([1, 2, 3])
    assert wait_for(lambda: output.played == [b"audio-1"])
    playlist.step(1)
    assert wait_for(lambda: output.played == [b"audio-1", b"audio-2"])
    playlist.step(-1)
    assert wait_for(lambda: output.played[-1] == b"audio-1" and len(output.played) == 3)
    playlist.step(-1)  # before the first: the playlist stops
    assert wait_for(lambda: not playlist.playing) and changes[-1] is None


def test_starting_again_replaces_the_running_list(output: FakeOutput) -> None:
    output.duration = 5.0
    playlist, _, _, fetched = make(output)
    playlist.start([1, 2])
    assert wait_for(lambda: fetched == [1])
    playlist.start([7, 8])
    assert wait_for(lambda: 7 in fetched)
    assert 2 not in fetched  # the old list never reached its second quote
    playlist.stop()


def test_empty_list_and_idle_calls_do_nothing(output: FakeOutput) -> None:
    playlist, changes, _, _ = make(output)
    playlist.start([])
    playlist.step(1)
    playlist.stop(notify=False)
    assert changes == [] and not playlist.playing


def test_a_slow_fetch_that_finishes_after_stop_never_plays(output: FakeOutput) -> None:
    release = threading.Event()
    changes: list[int | None] = []

    def slow_fetch(note_id: int) -> tuple[bytes, str]:
        release.wait(2)
        return b"late", "wav"

    playlist = QuotePlaylist(slow_fetch, output, changes.append, poll_seconds=0.005)
    playlist.start([1])
    assert wait_for(lambda: changes == [0])
    playlist.stop()
    release.set()
    assert not wait_for(lambda: output.played, timeout=0.3)
