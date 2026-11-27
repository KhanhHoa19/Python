"""Background sound and the chapter chime (no sound card: a fake output records what was asked of it)."""

from __future__ import annotations

import io
import time
import wave

from conftest import FakeOutput, wait_for
from test_controller import FakeApi, FakeListener

from player.ambient import AmbientPlayer
from player.chime import CHIME_SECONDS, SAMPLE_RATE, make_chime_wav
from player.controller import ReaderController


def test_chime_is_a_short_quiet_wav() -> None:
    with wave.open(io.BytesIO(make_chime_wav()), "rb") as wav:
        assert wav.getframerate() == SAMPLE_RATE and wav.getnchannels() == 1
        assert abs(wav.getnframes() / wav.getframerate() - CHIME_SECONDS) < 0.01
        frames = wav.readframes(wav.getnframes())
    peak = max(abs(int.from_bytes(frames[i:i + 2], "little", signed=True)) for i in range(0, len(frames), 2))
    assert 3000 < peak < 0.5 * 32767  # audible but soft


def _player(output: FakeOutput, fetched: list[int]) -> AmbientPlayer:
    def fetch(track_id: int) -> tuple[bytes, str]:
        fetched.append(track_id)
        return f"sound-{track_id}".encode(), "mp3"

    return AmbientPlayer(output, fetch=fetch)


def test_ambient_follows_the_reader_and_downloads_each_track_once() -> None:
    output, fetched = FakeOutput(), []
    player = _player(output, fetched)
    player.configure(7, 0.5)
    player.set_playing(False)
    assert output.ambient is None and fetched == []  # nothing is downloaded until the reader plays

    player.set_playing(True)
    assert wait_for(lambda: output.ambient is not None)
    assert output.ambient == {"data": b"sound-7", "volume": 0.5, "playing": True}

    player.set_playing(False)
    assert output.ambient["playing"] is False  # paused with the reader
    player.set_playing(True)
    assert output.ambient["playing"] is True and fetched == [7]  # resumed from memory, no second download


def test_ambient_volume_track_change_and_off() -> None:
    output, fetched = FakeOutput(), []
    player = _player(output, fetched)
    player.set_playing(True)
    player.configure(1, 0.4)
    assert wait_for(lambda: output.ambient is not None)
    player.configure(1, 0.8)
    assert output.ambient["volume"] == 0.8
    player.set_fade(0.5)  # the sleep timer fades the background too
    assert abs(output.ambient["volume"] - 0.4) < 1e-9

    player.configure(2, 0.8)  # another track replaces it
    assert wait_for(lambda: output.ambient is not None and output.ambient["data"] == b"sound-2")
    player.configure(0, 0.8)  # "Tắt"
    assert output.ambient is None or output.ambient["playing"] is False
    assert fetched == [1, 2]


def test_a_failing_download_never_stops_the_reader() -> None:
    output = FakeOutput()

    def broken(track_id: int) -> tuple[bytes, str]:
        raise OSError("offline")

    player = AmbientPlayer(output, fetch=broken)
    player.configure(3, 0.4)
    player.set_playing(True)
    time.sleep(0.2)
    assert output.ambient is None


def _chapters(api: FakeApi) -> None:
    for i, sentence in enumerate(api.sentences):
        sentence["chapter_index"] = 1 if i < 2 else 2  # sentences 0-1 are chapter 1, 2-3 are chapter 2


def _controller(api: FakeApi, output: FakeOutput) -> tuple[ReaderController, FakeListener]:
    listener = FakeListener()
    controller = ReaderController(api, output, listener)  # type: ignore[arg-type]
    controller.load_book(1, "Sách")
    return controller, listener


def _run_to_end(controller: ReaderController, listener: FakeListener) -> None:
    controller.play(0)
    assert wait_for(lambda: "finished" in listener.states, timeout=8)


def test_chime_plays_once_between_chapters_when_the_story_continues() -> None:
    api, output = FakeApi(sentences=4), FakeOutput()
    _chapters(api)
    controller, listener = _controller(api, output)
    chime = make_chime_wav()
    _run_to_end(controller, listener)
    assert output.played.count(chime) == 1
    # The chime sits right between the last sentence of chapter 1 and the first of chapter 2.
    assert [p == chime for p in output.played] == [False, False, True, False, False]


def test_no_chime_when_switched_off_or_when_jumping_into_a_chapter() -> None:
    api, output = FakeApi(sentences=4), FakeOutput()
    _chapters(api)
    controller, listener = _controller(api, output)
    controller.chapter_chime = False
    _run_to_end(controller, listener)
    assert make_chime_wav() not in output.played

    api2, output2 = FakeApi(sentences=4), FakeOutput()
    _chapters(api2)
    controller2, listener2 = _controller(api2, output2)
    controller2.play(2)  # starts straight in chapter 2: nothing came before it, so no chime
    assert wait_for(lambda: "finished" in listener2.states, timeout=8)
    assert make_chime_wav() not in output2.played


def test_background_sound_plays_only_while_the_reader_plays() -> None:
    api, output = FakeApi(sentences=3), FakeOutput(duration=0.2)
    controller, _ = _controller(api, output)
    controller.ambient._fetch = lambda track_id: (b"rain", "mp3")
    controller.ambient.configure(5, 0.3)
    assert output.ambient is None  # idle: silent
    controller.play(0)
    assert wait_for(lambda: output.ambient is not None and output.ambient["playing"])
    controller.toggle()  # pause
    assert output.ambient["playing"] is False
    controller.toggle()  # resume
    assert output.ambient["playing"] is True
    controller.stop()
    assert output.ambient["playing"] is False
