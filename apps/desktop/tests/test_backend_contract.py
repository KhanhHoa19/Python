"""Desktop <-> real backend contract: ApiClient and ReaderController against the FastAPI app.

Skipped automatically when the backend (or its dependencies) is not available.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from api_client import ApiClient, ApiError  # noqa: E402
from conftest import FakeOutput, make_wav, wait_for  # noqa: E402
from player.controller import ReaderController  # noqa: E402


def test_ingest_list_sentences_and_delete(api: ApiClient, book: dict) -> None:
    assert book["total_sentences"] == 3
    assert [b["title"] for b in api.list_books()] == ["Bài học"]
    sentences = api.get_sentences(book["book_id"])
    assert [s["text_content"] for s in sentences][0] == "Xin chào các bạn."
    api.delete_book(book["book_id"])
    assert api.list_books() == []
    with pytest.raises(ApiError) as info:
        api.get_sentences(book["book_id"])
    assert info.value.status == 404


def test_upload_unsupported_file_reports_backend_message(api: ApiClient, tmp_path) -> None:
    bad = tmp_path / "x.exe"
    bad.write_bytes(b"MZ")
    with pytest.raises(ApiError) as info:
        api.ingest_book(bad)
    assert info.value.status == 400 and "Unsupported file format" in info.value.message


def test_audio_bookmark_and_session_roundtrip(api: ApiClient, book: dict) -> None:
    data, ext = api.fetch_audio(book["book_id"], 0, speed=1.0)
    assert ext == "wav" and data[:4] == b"RIFF"
    api.save_bookmark(book["book_id"], 1, 2, 100.0)
    assert api.get_bookmark(book["book_id"])["current_sentence_index"] == 2
    api.record_session({
        "book_id": book["book_id"], "start_time": "2026-11-26T08:00:00+00:00",
        "end_time": "2026-11-26T08:01:00+00:00", "duration_seconds": 60.0,
        "sentences_read": 3, "words_read": 30,
    })


def test_settings_and_quota_error_reach_client_as_flags(api: ApiClient, book: dict) -> None:
    current = api.get_settings()
    api.update_settings({**{k: current[k] for k in
                            ("prefetch_count", "default_speed", "default_voice")}, "daily_char_limit": 5})
    with pytest.raises(ApiError) as info:
        api.fetch_audio(book["book_id"], 0)
    assert info.value.is_quota_error


def test_voices_clone_preview_delete(api: ApiClient) -> None:
    voices = api.list_voices()
    assert voices["supports_cloning"] and voices["voices"]
    sample = Path(__file__).parent / "_sample.wav"
    sample.write_bytes(make_wav(6))
    try:
        created = api.clone_voice(sample, "Giọng thử", "vi", "female", consent=True)
        with pytest.raises(ApiError) as info:
            api.clone_voice(sample, "Không đồng ý", "vi", "female", consent=False)
        assert info.value.status == 400
    finally:
        sample.unlink(missing_ok=True)
    assert api.list_voices()["voices"][0]["voice_id"] == created["voice_id"]
    data, ext = api.preview_voice(created["voice_id"])
    assert ext == "wav" and data[:4] == b"RIFF"
    api.delete_voice(created["voice_id"])


def test_notes_roundtrip_with_audio(api: ApiClient, book: dict) -> None:
    note = api.create_note(book["book_id"], 0, 0, 8, "ghi nhớ")
    assert note["excerpt"] == "Xin chào"
    assert api.list_notes(book["book_id"])[0]["id"] == note["id"]
    assert api.update_note(note["id"], "đã sửa")["note_text"] == "đã sửa"
    data, _ = api.note_audio(note["id"])
    assert data[:4] == b"RIFF"
    api.delete_note(note["id"])
    assert api.list_notes() == []


def test_export_flow_and_download(api: ApiClient, book: dict, tmp_path) -> None:
    estimate = api.export_estimate(book["book_id"])
    assert estimate["sentences"] == 3
    job = api.start_export(book["book_id"])
    assert wait_for(lambda: api.export_status(job["job_id"])["status"] != "running")
    status = api.export_status(job["job_id"])
    assert status["status"] == "done", status
    target = tmp_path / status["file_name"]
    api.download_export(job["job_id"], target)
    assert target.read_bytes()[:4] == b"RIFF"


def test_health_and_analytics_shapes(api: ApiClient) -> None:
    assert api.health()["status"] == "ok"
    assert api.network_health()["skipped"] is True
    assert api.verify_tts()["ok"] is True
    daily = api.analytics_daily(7)
    assert len(daily) == 7 and {"date", "minutes", "words", "sessions"} <= set(daily[0])
    assert {"avg_latency_ms", "p95_latency_ms", "success_rate", "words_per_minute"} <= set(api.analytics_metrics(7))


def test_reader_controller_plays_a_book_end_to_end(api: ApiClient, book: dict) -> None:
    """The real thing: controller + engine + ApiClient + backend; only the speaker is fake."""
    output = FakeOutput(duration=0.02)
    states: list[str] = []

    class Listener:
        def on_position(self, index: int) -> None: ...
        def on_state(self, state: str) -> None:
            states.append(state)

        def on_warning(self, message: str) -> None:
            states.append(f"warn:{message}")

        def on_error(self, message: str) -> None:
            states.append(f"error:{message}")

    controller = ReaderController(api, output, Listener())  # type: ignore[arg-type]
    controller.load_book(book["book_id"], "Bài học")
    controller.play()
    assert wait_for(lambda: "finished" in states, timeout=10), states
    assert len(output.played) == 3

    assert wait_for(lambda: api.get_bookmark(book["book_id"])["current_sentence_index"] == 2)
    assert api.get_bookmark(book["book_id"])["completion_percentage"] == 100.0
    daily = api.analytics_daily(1)
    assert wait_for(lambda: api.analytics_daily(1)[-1]["sessions"] == 1), daily
    assert api.analytics_daily(1)[-1]["words"] > 0
