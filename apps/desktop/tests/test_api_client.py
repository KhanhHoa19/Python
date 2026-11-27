"""ApiClient against a fake backend (httpx.MockTransport)."""

from __future__ import annotations

import httpx
import pytest

from api_client import ApiClient, ApiError


def make_client(handler) -> ApiClient:
    return ApiClient(base_url="http://test", transport=httpx.MockTransport(handler))


def test_list_books_returns_json() -> None:
    client = make_client(lambda req: httpx.Response(200, json=[{"id": 1, "title": "A"}]))
    assert client.list_books() == [{"id": 1, "title": "A"}]


def test_error_message_taken_from_backend_error_field() -> None:
    client = make_client(lambda req: httpx.Response(404, json={"error": "Book 9 not found"}))
    with pytest.raises(ApiError) as info:
        client.get_sentences(9)
    assert info.value.status == 404 and info.value.message == "Book 9 not found"


def test_non_json_error_falls_back_to_status() -> None:
    client = make_client(lambda req: httpx.Response(502, text="bad gateway"))
    with pytest.raises(ApiError) as info:
        client.health()
    assert info.value.message == "HTTP 502"


def test_connection_failure_becomes_api_error_status_zero() -> None:
    def refuse(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(ApiError) as info:
        make_client(refuse).health()
    assert info.value.is_connection_error


def test_timeout_becomes_connection_style_error() -> None:
    def slow(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    with pytest.raises(ApiError) as info:
        make_client(slow).health()
    assert info.value.status == 0 and "chậm" in info.value.message


def test_fetch_audio_sends_speed_and_voice_and_detects_extension() -> None:
    seen: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.update(dict(req.url.params), path=req.url.path)
        return httpx.Response(200, content=b"RIFF", headers={"content-type": "audio/wav"})

    data, ext = make_client(handler).fetch_audio(3, 7, speed=1.25, voice="v1")
    assert (data, ext) == (b"RIFF", "wav")
    assert seen == {"speed": "1.25", "voice": "v1", "path": "/api/audio/3/7"}


def test_quota_error_flag() -> None:
    client = make_client(lambda req: httpx.Response(429, json={"error": "Daily character limit reached."}))
    with pytest.raises(ApiError) as info:
        client.fetch_audio(1, 0)
    assert info.value.is_quota_error


def test_ingest_uploads_file_with_title(tmp_path) -> None:
    sample = tmp_path / "a.txt"
    sample.write_text("Xin chào.", encoding="utf-8")
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = req.read()
        return httpx.Response(201, json={"book_id": 1, "total_sentences": 1})

    result = make_client(handler).ingest_book(sample, title="Tiêu đề")
    assert result["book_id"] == 1
    assert b'name="file"; filename="a.txt"' in captured["body"] and "Tiêu đề".encode() in captured["body"]


def test_clone_voice_sends_consent_flag(tmp_path) -> None:
    sample = tmp_path / "s.wav"
    sample.write_bytes(b"RIFF")
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = req.read()
        return httpx.Response(201, json={"voice_id": "x"})

    make_client(handler).clone_voice(sample, "Tôi", "vi", "female", consent=True)
    assert b'name="consent"\r\n\r\ntrue' in captured["body"]


def test_download_export_writes_file(tmp_path) -> None:
    client = make_client(lambda req: httpx.Response(200, content=b"audio-bytes"))
    target = tmp_path / "out.wav"
    client.download_export("job1", target)
    assert target.read_bytes() == b"audio-bytes"


def test_rename_book_sends_patch_with_the_new_title() -> None:
    seen: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.update(method=req.method, path=req.url.path, body=req.read())
        return httpx.Response(200, json={"id": 4, "title": "Tên mới"})

    result = make_client(handler).rename_book(4, "Tên mới")
    assert result["title"] == "Tên mới"
    assert seen["method"] == "PATCH" and seen["path"] == "/api/books/4"
    assert "Tên mới".encode() in seen["body"] or b"T\\u00ean" in seen["body"]


def test_rename_book_error_is_reported_as_api_error() -> None:
    client = make_client(lambda req: httpx.Response(400, json={"error": "Validation error"}))
    with pytest.raises(ApiError) as info:
        client.rename_book(4, "x")
    assert info.value.status == 400
