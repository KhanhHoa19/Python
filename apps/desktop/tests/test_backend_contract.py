"""Desktop <-> real backend contract: ApiClient and ReaderController against the FastAPI app.

Skipped automatically when the backend (or its dependencies) is not available.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from conftest import FakeOutput, make_wav, wait_for

from api_client import ApiClient, ApiError
from player.controller import ReaderController


def test_ingest_list_sentences_and_delete(api: ApiClient, book: dict) -> None:
    assert book["total_sentences"] == 3
    assert [b["title"] for b in api.list_books()] == ["Bài học"]
    sentences = api.get_sentences(book["book_id"])
    assert sentences[0]["text_content"] == "Xin chào các bạn."
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


def test_voice_is_remembered_and_counted(api: ApiClient, book: dict) -> None:
    api.save_bookmark(book["book_id"], 1, 1, 50.0, "mock-vi-male")
    assert api.get_bookmark(book["book_id"])["voice"] == "mock-vi-male"
    api.save_bookmark(book["book_id"], 1, 2, 100.0)  # no voice: keeps the remembered one
    assert api.get_bookmark(book["book_id"])["voice"] == "mock-vi-male"
    now = datetime.now(UTC)
    api.record_session({
        "book_id": book["book_id"], "start_time": (now - timedelta(seconds=90)).isoformat(),
        "end_time": now.isoformat(), "duration_seconds": 90.0,
        "sentences_read": 2, "words_read": 20, "voice": "mock-vi-male",
    })
    stats = {row["voice"]: row for row in api.analytics_voices(7)}
    assert stats["mock-vi-male"]["minutes"] == 1.5 and stats["mock-vi-male"]["sessions"] == 1


def test_chapters_reach_the_client(api: ApiClient, book: dict) -> None:
    chapters = api.get_chapters(book["book_id"])
    assert chapters and chapters[0]["start_sentence_index"] == 0
    assert all({"chapter_index", "title", "end_sentence_index", "sentence_count", "word_count"} <= set(c) for c in chapters)
    with pytest.raises(ApiError) as info:
        api.get_chapters(999_999)
    assert info.value.status == 404


def test_shelf_filters_counts_and_actions(api: ApiClient, admin_api: ApiClient, book: dict, tmp_path) -> None:
    other = tmp_path / "khac.txt"
    other.write_text("Một câu rất khác. Câu thứ hai khác nữa.", encoding="utf-8")
    categories = api.list_categories()
    tech = next(c for c in categories if c["slug"] == "cong-nghe")
    second = api.ingest_book(other, "Lập trình Python", "Ada", category_id=tech["id"])
    assert api.shelf_counts() == {"unread": 2, "reading": 0, "completed": 0, "favorite": 0}
    assert [b["title"] for b in api.list_books(q="lap trinh")] == ["Lập trình Python"]  # accent-free search
    assert [b["title"] for b in api.list_books(category="cong-nghe")] == ["Lập trình Python"]
    api.set_favorite(second["book_id"], True)
    api.set_read_status(book["book_id"], "completed")
    assert api.shelf_counts() == {"unread": 1, "reading": 0, "completed": 1, "favorite": 1}
    assert [b["title"] for b in api.list_books(status="favorite")] == ["Lập trình Python"]
    api.set_read_status(book["book_id"], "unread")
    assert api.list_books(status="completed") == []
    updated = api.update_book(second["book_id"], title="Python nâng cao", category_id=None)
    assert updated["title"] == "Python nâng cao" and updated["category"] is None


def test_catalogue_add_and_remove(api: ApiClient, admin_api: ApiClient, tmp_path) -> None:
    sample = tmp_path / "chung.txt"
    sample.write_text("Câu một của sách chung. Câu hai của sách chung.", encoding="utf-8")
    public = admin_api.ingest_book(sample, "Sách chung", is_public=True)
    listed = api.explore_books()
    assert [(b["title"], b["on_shelf"]) for b in listed] == [("Sách chung", False)]
    assert api.list_books() == []  # not on the member's shelf yet
    api.add_to_shelf(public["book_id"])
    assert [b["title"] for b in api.list_books(source="system")] == ["Sách chung"]
    assert api.explore_books()[0]["on_shelf"] is True
    api.remove_from_shelf(public["book_id"])
    assert api.list_books() == []


def test_covers_are_generated_downloadable_and_replaceable(api: ApiClient, book: dict, tmp_path) -> None:
    from PIL import Image

    detail = api.list_books()[0]
    assert detail["cover_url"].startswith("/api/covers/")
    data = api.cover_bytes(detail["cover_url"])
    assert data[:2] == b"\xff\xd8" and Image.open(io.BytesIO(data)).size == (400, 533)
    picture = tmp_path / "bia.png"
    Image.new("RGB", (600, 900), "green").save(picture)
    replaced = api.replace_cover(book["book_id"], picture)
    assert replaced["cover_url"] != detail["cover_url"]
    with pytest.raises(ApiError) as gone:
        api.cover_bytes(detail["cover_url"])  # the old image is deleted
    assert gone.value.status == 404


def test_cancel_unknown_export_is_404(api: ApiClient) -> None:
    with pytest.raises(ApiError) as info:
        api.cancel_export("nope")
    assert info.value.status == 404


def test_settings_and_quota_error_reach_client_as_flags(api: ApiClient, admin_api: ApiClient, book: dict) -> None:
    current = api.get_settings()
    same = {k: current[k] for k in ("prefetch_count", "default_speed", "default_voice")}
    api.update_settings({**same, "daily_char_limit": 5})  # a member's value for the shared limit is ignored
    assert api.get_settings()["daily_char_limit"] == 0
    admin_api.update_settings({**same, "daily_char_limit": 5})  # an admin sets it for everyone
    assert api.get_settings()["daily_char_limit"] == 5
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
    assert api.update_note(note["id"], note_text="đã sửa")["note_text"] == "đã sửa"
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


def test_health_and_analytics_shapes(api: ApiClient, admin_api: ApiClient) -> None:
    from api_client import ApiError

    assert api.health()["status"] == "ok"
    for call in (api.network_health, api.verify_tts):  # the shared TTS account: administrators only
        with pytest.raises(ApiError) as denied:
            call()
        assert denied.value.status == 403
    assert admin_api.network_health()["skipped"] is True
    assert admin_api.verify_tts()["ok"] is True
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


def test_rename_book_against_the_real_backend(api: ApiClient, book: dict) -> None:
    renamed = api.rename_book(book["book_id"], "  Thung   lũng khủng khiếp ")
    assert renamed["title"] == "Thung lũng khủng khiếp"
    assert api.list_books()[0]["title"] == "Thung lũng khủng khiếp"
    with pytest.raises(ApiError) as info:
        api.rename_book(book["book_id"], "   ")
    assert info.value.status == 400
    with pytest.raises(ApiError) as missing:
        api.rename_book(9999, "x")
    assert missing.value.status == 404


def test_quotes_one_tap_tag_filter_and_audio(api: ApiClient, book: dict) -> None:
    first = api.create_note(book["book_id"], 1)  # no offsets: the whole sentence
    assert first["excerpt"] == "Đây là câu thứ hai." and first["has_audio"] and first["emotion_tag"] is None
    assert first["context_before"] == "Xin chào các bạn." and first["context_after"] == "Và đây là câu thứ ba."
    again = api.create_note(book["book_id"], 1, emotion_tag="touching")  # the same sentence: one quote, now tagged
    assert again["id"] == first["id"] and again["emotion_tag"] == "touching"
    api.create_note(book["book_id"], 0, 0, 4, "ghi", emotion_tag="funny")
    assert len(api.list_notes()) == 2
    assert [n["id"] for n in api.list_notes(emotion_tag="touching")] == [first["id"]]
    assert api.update_note(first["id"], emotion_tag=None)["emotion_tag"] is None
    data, ext = api.note_audio(first["id"])
    assert data and ext
    api.delete_note(first["id"])
    assert len(api.list_notes(book_id=book["book_id"])) == 1
    with pytest.raises(ApiError) as bad:
        api.create_note(book["book_id"], 1, emotion_tag="angry")
    assert bad.value.status == 400


def test_admin_api_and_voice_studio(api: ApiClient, admin_api: ApiClient, tmp_path) -> None:
    from api_client import ApiError

    # A normal account is refused everywhere in the panel.
    for call in (api.admin_books, api.admin_categories, api.admin_voices, api.admin_users):
        with pytest.raises(ApiError) as denied:
            call()
        assert denied.value.status == 403

    # Categories: create, rename, count, delete.
    created = admin_api.create_category("Văn Hóa", "feather", "#336699")
    assert created["slug"] == "van-hoa" and created["book_count"] == 0
    assert admin_api.update_category(created["id"], "Văn hóa Việt", "feather", "#112233")["name"] == "Văn hóa Việt"
    assert created["id"] in {c["id"] for c in api.list_categories()}
    admin_api.delete_category(created["id"])
    with pytest.raises(ApiError) as protected:
        admin_api.delete_category(next(c["id"] for c in admin_api.admin_categories() if c["slug"] == "khac"))
    assert protected.value.status == 400

    # Voices: the admin shares a clone, makes it the system default; a member sees it as shared.
    sample = tmp_path / "mau.wav"
    sample.write_bytes(make_wav(6))
    voice = admin_api.clone_voice(sample, "Giọng chung", "vi", "female", consent=True)
    assert admin_api.set_voice_public(voice["voice_id"], True)["is_public"] is True
    assert admin_api.set_default_voice(voice["voice_id"])["default_voice"] == voice["voice_id"]
    shared = next(v for v in api.list_voices()["voices"] if v["voice_id"] == voice["voice_id"])
    assert shared["is_public"] and not shared["is_mine"]
    assert api.get_settings()["default_voice"] == voice["voice_id"]
    assert admin_api.rename_voice(voice["voice_id"], "Giọng mới")["display_name"] == "Giọng mới"
    with pytest.raises(ApiError) as other:
        api.rename_voice(voice["voice_id"], "hack")
    assert other.value.status == 403

    users = {u["username"]: u for u in admin_api.admin_users()}
    assert users["tester"]["role"] == "user" and users["admin"]["voice_count"] == 1
