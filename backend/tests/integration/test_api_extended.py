"""Integration tests for voices, notes, settings, health, export, analytics and document upload."""

from __future__ import annotations

import io
import wave
from collections.abc import Generator
from contextlib import ExitStack
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from src.api.app import create_app
from src.core.config import get_settings
from src.core.models.book import Book, BookSentence
from src.core.models.telemetry import NetworkMetric
from src.core.network.diagnostics import CheckResult
from src.core.storage.repositories import SqlBookRepository, SqlTelemetryRepository
from src.core.tts.base import TTSProviderError
from src.core.tts.mock_adapter import MockProvider
from tests.auth_helpers import TESTER_ID, sign_in, tester, use_engine, user_by_name


class NoCloneProvider(MockProvider):
    @property
    def supports_cloning(self) -> bool:
        return False


class FailingVerifyProvider(MockProvider):
    def verify(self) -> None:
        raise TTSProviderError("invalid API key")


def make_wav(seconds: float) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * int(seconds * 8000))
    return buf.getvalue()


def make_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref)
    return out


@pytest.fixture
def provider() -> MockProvider:
    return MockProvider()


@pytest.fixture
def client(
    test_engine: Engine, provider: MockProvider, tmp_path, monkeypatch
) -> Generator[TestClient, None, None]:
    for var, name in (
        ("AUDIO_CACHE_DIR", "cache"), ("EXPORT_DIR", "exports"), ("VOICE_SAMPLES_DIR", "samples")
    ):
        monkeypatch.setenv(var, str(tmp_path / name))
    get_settings.cache_clear()
    with ExitStack() as stack:
        stack.enter_context(use_engine(test_engine))
        for target in (
            "src.core.player.audio_service.TTSFactory",
            "src.api.routes.voices.TTSFactory",
            "src.api.routes.settings.TTSFactory",
            "src.api.routes.health.TTSFactory",
        ):
            stack.enter_context(patch(target)).create_provider.return_value = provider
        with TestClient(create_app()) as test_client:
            yield sign_in(test_client, test_engine, tester(test_engine))
    get_settings.cache_clear()


@pytest.fixture
def admin_client(client: TestClient, test_engine: Engine) -> Generator[TestClient, None, None]:
    """A second client on the same app, signed in as the administrator."""
    with TestClient(client.app) as other:
        yield sign_in(other, test_engine, user_by_name(test_engine, "admin"))


def add_book(engine: Engine, texts: list[str] | None = None) -> int:
    texts = texts or ["Xin chào các bạn.", "Đây là câu thứ hai."]
    sentences = [
        BookSentence(
            id=None, book_id=0, chapter_index=1, sentence_index=i, text_content=t,
            word_count=len(t.split()), content_hash=f"{i:064d}",
        )
        for i, t in enumerate(texts)
    ]
    book = Book(owner_id=TESTER_ID,
        id=None, title="Sách Thử Nghiệm", author="A", source_path="x.txt", content_hash="f" * 64,
        total_chapters=1, total_sentences=len(texts), total_words=sum(s.word_count for s in sentences),
    )
    return SqlBookRepository(engine).save_book(book, sentences)


# ---------------------------------------------------------------- books / upload


def test_delete_book(client: TestClient, test_engine: Engine) -> None:
    book_id = add_book(test_engine)
    assert client.delete(f"/api/books/{book_id}").status_code == 204
    assert client.get(f"/api/books/{book_id}").status_code == 404
    assert client.delete(f"/api/books/{book_id}").status_code == 404


def test_rename_book_trims_and_persists(client: TestClient, test_engine: Engine) -> None:
    book_id = add_book(test_engine)
    resp = client.patch(f"/api/books/{book_id}", json={"title": "  Sherlock   Holmes \n tập một "})
    assert resp.status_code == 200 and resp.json()["title"] == "Sherlock Holmes tập một"
    assert client.get(f"/api/books/{book_id}").json()["title"] == "Sherlock Holmes tập một"
    assert [b["title"] for b in client.get("/api/books").json()] == ["Sherlock Holmes tập một"]


def test_rename_updates_the_title_shown_on_notes(client: TestClient, test_engine: Engine) -> None:
    book_id = add_book(test_engine)
    client.post("/api/notes", json={"book_id": book_id, "sentence_index": 0, "start_offset": 0, "end_offset": 3})
    client.patch(f"/api/books/{book_id}", json={"title": "Tên mới"})
    assert client.get("/api/notes").json()[0]["book_title"] == "Tên mới"


@pytest.mark.parametrize("title", ["", "   ", "\n\t", "x" * 256])
def test_rename_rejects_empty_or_too_long_titles(client: TestClient, test_engine: Engine, title: str) -> None:
    book_id = add_book(test_engine)
    resp = client.patch(f"/api/books/{book_id}", json={"title": title})
    assert resp.status_code == 400
    assert client.get(f"/api/books/{book_id}").json()["title"] == "Sách Thử Nghiệm"  # unchanged


def test_rename_accepts_exactly_255_characters_and_keeps_vietnamese(client: TestClient, test_engine: Engine) -> None:
    book_id = add_book(test_engine)
    assert client.patch(f"/api/books/{book_id}", json={"title": "ế" * 255}).status_code == 200
    assert client.patch(f"/api/books/{book_id}", json={"title": "Thung lũng khủng khiếp"}).json()["title"] == (
        "Thung lũng khủng khiếp"
    )


def test_rename_unknown_book_and_missing_field(client: TestClient) -> None:
    assert client.patch("/api/books/999", json={"title": "x"}).status_code == 404
    assert client.patch("/api/books/1", json={}).status_code == 400


def test_ingest_pdf_and_docx(client: TestClient) -> None:
    pdf = make_pdf("The first sentence is here. The second one follows it.")
    resp = client.post("/api/books/ingest", files={"file": ("doc.pdf", io.BytesIO(pdf))})
    assert resp.status_code == 201
    assert resp.json()["total_sentences"] >= 2

    from docx import Document

    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph("Xin chào các bạn. Đây là tài liệu Word.")
    doc.save(buf)
    resp = client.post("/api/books/ingest", files={"file": ("tai_lieu.docx", io.BytesIO(buf.getvalue()))})
    assert resp.status_code == 201
    assert resp.json()["total_sentences"] >= 2


def test_ingest_corrupt_pdf_and_scanned_pdf_return_400(client: TestClient) -> None:
    bad = client.post("/api/books/ingest", files={"file": ("a.pdf", io.BytesIO(b"not a pdf"))})
    assert bad.status_code == 400
    assert "Cannot read PDF" in bad.json()["error"]

    blank = make_pdf("")
    scanned = client.post("/api/books/ingest", files={"file": ("b.pdf", io.BytesIO(blank))})
    assert scanned.status_code == 400
    assert "OCR" in scanned.json()["error"]


# ---------------------------------------------------------------- voices


def test_list_voices_includes_provider_voices(client: TestClient) -> None:
    body = client.get("/api/voices").json()
    assert body["provider"] == "mock"
    assert body["supports_cloning"] is True
    assert {v["voice_id"] for v in body["voices"]} >= {"mock-vi-female", "mock-vi-male"}


def test_clone_voice_requires_consent(client: TestClient) -> None:
    resp = client.post(
        "/api/voices/clone", data={"name": "Tôi", "consent": "false"},
        files={"sample": ("s.wav", io.BytesIO(make_wav(6)))},
    )
    assert resp.status_code == 400
    assert "Consent" in resp.json()["error"]


def test_clone_voice_success_then_listed_and_deleted(client: TestClient) -> None:
    resp = client.post(
        "/api/voices/clone", data={"name": "Giọng của tôi", "consent": "true", "gender": "female"},
        files={"sample": ("s.wav", io.BytesIO(make_wav(6)))},
    )
    assert resp.status_code == 201
    voice = resp.json()
    assert voice["is_custom"] and voice["consent_at"]

    listed = client.get("/api/voices").json()["voices"]
    assert listed[0]["voice_id"] == voice["voice_id"] and listed[0]["is_custom"]

    assert client.delete(f"/api/voices/{voice['voice_id']}").status_code == 204
    assert client.delete(f"/api/voices/{voice['voice_id']}").status_code == 404


@pytest.mark.parametrize("seconds", [2, 20])
def test_clone_voice_rejects_bad_sample_length(client: TestClient, seconds: int) -> None:
    resp = client.post(
        "/api/voices/clone", data={"name": "x", "consent": "true"},
        files={"sample": ("s.wav", io.BytesIO(make_wav(seconds)))},
    )
    assert resp.status_code == 400
    assert "5-15" in resp.json()["error"]


def test_clone_voice_not_supported_returns_501(client: TestClient) -> None:
    with patch("src.api.routes.voices.TTSFactory") as factory:
        factory.create_provider.return_value = NoCloneProvider()
        resp = client.post(
            "/api/voices/clone", data={"name": "x", "consent": "true"},
            files={"sample": ("s.wav", io.BytesIO(make_wav(6)))},
        )
    assert resp.status_code == 501


class LongSampleProvider(MockProvider):
    @property
    def clone_sample_seconds(self) -> tuple[float, float]:
        return (5.0, 180.0)


class DeleteFailsProvider(MockProvider):
    def delete_voice(self, voice_id: str) -> None:
        raise TTSProviderError("provider is down")


class ListsItsClonesProvider(MockProvider):
    """Like HeyGen: the provider's own voice list also contains the voices you cloned."""

    def clone_voice(self, sample_path: str, name: str, language: str = "vi") -> str:
        return "cloned-1"

    def list_voices(self):  # type: ignore[no-untyped-def]
        from src.core.tts.base import VoiceInfo

        return [*super().list_voices(), VoiceInfo("cloned-1", "Giọng clone", "vi", None, "HeyGen")]


def test_a_cloned_voice_is_listed_once_even_if_the_provider_lists_it_too(client: TestClient) -> None:
    with patch("src.api.routes.voices.TTSFactory") as factory:
        factory.create_provider.return_value = ListsItsClonesProvider()
        before = client.get("/api/voices").json()["voices"]
        assert [v["voice_id"] for v in before].count("cloned-1") == 1 and not before[-1]["is_custom"]
        client.post("/api/voices/clone", data={"name": "Giọng clone", "consent": "true"},
                    files={"sample": ("s.wav", io.BytesIO(make_wav(6)))})
        after = client.get("/api/voices").json()["voices"]
    entries = [v for v in after if v["voice_id"] == "cloned-1"]
    assert len(entries) == 1 and entries[0]["is_custom"] and entries[0]["consent_at"]


def test_bookmark_and_session_for_a_deleted_book_are_404_not_500(client: TestClient, test_engine: Engine) -> None:
    book_id = add_book(test_engine)
    assert client.delete(f"/api/books/{book_id}").status_code == 204
    bookmark = {"book_id": book_id, "current_chapter": 1, "current_sentence_index": 0, "completion_percentage": 0}
    assert client.post("/api/bookmarks", json=bookmark).status_code == 404
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    session = {"book_id": book_id, "start_time": now, "end_time": now, "duration_seconds": 5,
               "sentences_read": 1, "words_read": 3}
    assert client.post("/api/sessions", json=session).status_code == 404


def test_voice_list_exposes_the_providers_sample_length_range(client: TestClient) -> None:
    assert client.get("/api/voices").json()["clone_sample_seconds"] == [5.0, 15.0]
    with patch("src.api.routes.voices.TTSFactory") as factory:
        factory.create_provider.return_value = LongSampleProvider()
        assert client.get("/api/voices").json()["clone_sample_seconds"] == [5.0, 180.0]


def test_clone_accepts_a_longer_sample_when_the_provider_allows_it(client: TestClient) -> None:
    files = {"sample": ("s.wav", io.BytesIO(make_wav(60)))}
    with patch("src.api.routes.voices.TTSFactory") as factory:
        factory.create_provider.return_value = LongSampleProvider()
        resp = client.post("/api/voices/clone", data={"name": "Dài", "consent": "true"}, files=files)
    assert resp.status_code == 201


def test_deleting_a_voice_failing_at_the_provider_keeps_it(client: TestClient) -> None:
    created = client.post(
        "/api/voices/clone", data={"name": "Giữ lại", "consent": "true"},
        files={"sample": ("s.wav", io.BytesIO(make_wav(6)))},
    ).json()
    with patch("src.api.routes.voices.TTSFactory") as factory:
        factory.create_provider.return_value = DeleteFailsProvider()
        resp = client.delete(f"/api/voices/{created['voice_id']}")
    assert resp.status_code == 502 and "provider is down" in resp.json()["error"]
    assert created["voice_id"] in [v["voice_id"] for v in client.get("/api/voices").json()["voices"]]


def test_preview_voice_returns_audio(client: TestClient) -> None:
    resp = client.get("/api/voices/mock-vi-female/preview")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("audio/")
    assert resp.content[:4] == b"RIFF"


# ---------------------------------------------------------------- notes


def test_note_lifecycle(client: TestClient, test_engine: Engine) -> None:
    book_id = add_book(test_engine)
    payload = {"book_id": book_id, "sentence_index": 0, "start_offset": 0, "end_offset": 7, "note_text": "nhớ"}
    created = client.post("/api/notes", json=payload)
    assert created.status_code == 201
    note = created.json()
    assert note["excerpt"] == "Xin chào"[:7] and note["book_title"] == "Sách Thử Nghiệm"

    assert client.get(f"/api/notes?book_id={book_id}").json()[0]["id"] == note["id"]
    patched = client.patch(f"/api/notes/{note['id']}", json={"note_text": "đã sửa"})
    assert patched.json()["note_text"] == "đã sửa"

    audio = client.get(f"/api/notes/{note['id']}/audio")
    assert audio.status_code == 200 and audio.content[:4] == b"RIFF"

    assert client.delete(f"/api/notes/{note['id']}").status_code == 204
    assert client.delete(f"/api/notes/{note['id']}").status_code == 404


def test_note_validation(client: TestClient, test_engine: Engine) -> None:
    book_id = add_book(test_engine)
    base = {"book_id": book_id, "sentence_index": 0, "start_offset": 0, "end_offset": 5}
    assert client.post("/api/notes", json={**base, "end_offset": 999}).status_code == 400
    assert client.post("/api/notes", json={**base, "start_offset": 5, "end_offset": 5}).status_code == 400
    assert client.post("/api/notes", json={**base, "sentence_index": 99}).status_code == 404
    assert client.post("/api/notes", json={**base, "book_id": 999}).status_code == 404


# ---------------------------------------------------------------- settings / quota


def test_settings_defaults_and_update(client: TestClient, admin_client: TestClient) -> None:
    body = client.get("/api/settings").json()
    assert body["prefetch_count"] == 2 and body["daily_char_limit"] == 0 and body["provider"] == "mock"

    new = {"prefetch_count": 3, "default_speed": 1.25, "default_voice": "mock-vi-male", "daily_char_limit": 1000}
    updated = client.put("/api/settings", json=new).json()
    assert updated["prefetch_count"] == 3 and updated["default_voice"] == "mock-vi-male"
    # The daily limit protects the shared TTS bill: an ordinary user's value is ignored ...
    assert client.get("/api/settings").json()["daily_char_limit"] == 0
    # ... but an admin sets it for everyone, and preferences stay personal.
    assert admin_client.put("/api/settings", json=new).json()["daily_char_limit"] == 1000
    assert client.get("/api/settings").json()["daily_char_limit"] == 1000
    assert admin_client.get("/api/settings").json()["prefetch_count"] == 3
    other = {**new, "prefetch_count": 5}
    client.put("/api/settings", json=other)
    assert admin_client.get("/api/settings").json()["prefetch_count"] == 3  # not changed by someone else


def test_settings_rejects_invalid_values(client: TestClient) -> None:
    bad = {"prefetch_count": 9, "default_speed": 1.0, "default_voice": "v", "daily_char_limit": 0}
    assert client.put("/api/settings", json=bad).status_code == 400


def test_daily_limit_blocks_new_synthesis_but_not_cached(
    client: TestClient, admin_client: TestClient, test_engine: Engine
) -> None:
    book_id = add_book(test_engine, ["Câu một.", "Câu hai dài hơn nhiều."])
    settings = {"prefetch_count": 2, "default_speed": 1.0, "default_voice": "mock-vi-female", "daily_char_limit": 10}
    admin_client.put("/api/settings", json=settings)

    assert client.get(f"/api/audio/{book_id}/0").status_code == 200  # 8 chars, fits
    assert client.get(f"/api/audio/{book_id}/0").status_code == 200  # cached, no quota use
    blocked = client.get(f"/api/audio/{book_id}/1")
    assert blocked.status_code == 429
    assert client.get("/api/settings").json()["chars_used_today"] == len("Câu một.")


# ---------------------------------------------------------------- health


def test_network_health_skipped_for_offline_provider(client: TestClient) -> None:
    body = client.get("/api/health/network").json()
    assert body["skipped"] is True and body["checks"] == []


def test_network_health_reports_checks(client: TestClient, provider: MockProvider) -> None:
    online = MockProvider()
    online.__class__ = type("Edge", (MockProvider,), {"provider_name": property(lambda self: "edge-tts")})
    fake = [CheckResult("dns", True, "ok"), CheckResult("port", False, "closed")]
    with patch("src.api.routes.health.TTSFactory") as factory, \
         patch("src.api.routes.health.run_network_checks", return_value=fake) as run:
        factory.create_provider.return_value = online
        body = client.get("/api/health/network").json()
    run.assert_called_once_with("speech.platform.bing.com")
    assert body["host"] == "speech.platform.bing.com"
    assert [c["ok"] for c in body["checks"]] == [True, False]


def test_verify_tts_ok_and_failure(client: TestClient) -> None:
    assert client.post("/api/tts/verify").json() == {"provider": "mock", "ok": True, "error": None}
    with patch("src.api.routes.health.TTSFactory") as factory:
        factory.create_provider.return_value = FailingVerifyProvider()
        body = client.post("/api/tts/verify").json()
    assert body["ok"] is False and "invalid API key" in body["error"]


# ---------------------------------------------------------------- export


def test_export_estimate_counts_cached_chars(client: TestClient, test_engine: Engine) -> None:
    book_id = add_book(test_engine, ["Câu một.", "Câu hai."])
    client.get(f"/api/audio/{book_id}/0")  # caches sentence 0 with default voice
    est = client.get(f"/api/books/{book_id}/export/estimate").json()
    assert est["sentences"] == 2
    assert est["chars_cached"] == len("Câu một.") and est["chars_to_synthesize"] == len("Câu hai.")


def test_export_wav_end_to_end(client: TestClient, test_engine: Engine) -> None:
    book_id = add_book(test_engine)
    started = client.post(f"/api/books/{book_id}/export", json={"format": "wav"})
    assert started.status_code == 202
    job_id = started.json()["job_id"]

    status = client.get(f"/api/exports/{job_id}").json()  # background task already finished
    assert status["status"] == "done" and status["done"] == status["total"] == 2
    assert status["file_name"].endswith(".wav")

    file_resp = client.get(f"/api/exports/{job_id}/file")
    assert file_resp.status_code == 200
    with wave.open(io.BytesIO(file_resp.content), "rb") as merged:
        assert merged.getnframes() > 0


class FlakyOnceProvider(MockProvider):
    """Fails the first attempt for every distinct text, then succeeds (a flaky free TTS service)."""

    def __init__(self) -> None:
        super().__init__()
        self.seen: set[str] = set()

    def synthesize(self, text, voice=None, speed=1.0):  # type: ignore[no-untyped-def]
        if text not in self.seen:
            self.seen.add(text)
            raise TTSProviderError("No audio was received.")
        return super().synthesize(text, voice, speed)


def test_export_retries_transient_provider_errors(client: TestClient, test_engine: Engine) -> None:
    book_id = add_book(test_engine)
    with patch("src.core.player.audio_service.TTSFactory") as factory:
        factory.create_provider.return_value = FlakyOnceProvider()
        job_id = client.post(f"/api/books/{book_id}/export", json={}).json()["job_id"]
        status = client.get(f"/api/exports/{job_id}").json()
    assert status["status"] == "done" and status["done"] == 2


def test_export_gives_up_after_second_failure(client: TestClient, test_engine: Engine) -> None:
    class AlwaysFails(MockProvider):
        def synthesize(self, text, voice=None, speed=1.0):  # type: ignore[no-untyped-def]
            raise TTSProviderError("service down")

    book_id = add_book(test_engine)
    with patch("src.core.player.audio_service.TTSFactory") as factory:
        factory.create_provider.return_value = AlwaysFails()
        job_id = client.post(f"/api/books/{book_id}/export", json={}).json()["job_id"]
        status = client.get(f"/api/exports/{job_id}").json()
    assert status["status"] == "failed" and "service down" in status["error"]


def test_export_format_mismatch_fails_cleanly(client: TestClient, test_engine: Engine) -> None:
    book_id = add_book(test_engine)
    job_id = client.post(f"/api/books/{book_id}/export", json={"format": "mp3"}).json()["job_id"]
    status = client.get(f"/api/exports/{job_id}").json()
    assert status["status"] == "failed" and "mp3" in status["error"]
    assert client.get(f"/api/exports/{job_id}/file").status_code == 409


def test_export_unknown_job_and_book(client: TestClient) -> None:
    assert client.get("/api/exports/nope").status_code == 404
    assert client.post("/api/books/999/export", json={}).status_code == 404


# ---------------------------------------------------------------- analytics


def test_daily_stats_zero_filled_and_counts_today(client: TestClient, test_engine: Engine) -> None:
    book_id = add_book(test_engine)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    client.post("/api/sessions", json={
        "book_id": book_id, "start_time": now, "end_time": now,
        "duration_seconds": 120, "sentences_read": 3, "words_read": 40,
    })
    daily = client.get("/api/analytics/daily?days=7").json()
    assert len(daily) == 7
    assert daily[-1]["minutes"] == 2.0 and daily[-1]["words"] == 40
    assert sum(d["sessions"] for d in daily[:-1]) == 0


def test_metrics_latency_and_success_rate(client: TestClient, test_engine: Engine) -> None:
    book_id = add_book(test_engine)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    session_id = client.post("/api/sessions", json={
        "book_id": book_id, "start_time": now, "end_time": now,
        "duration_seconds": 60, "sentences_read": 2, "words_read": 150,
    }).json()["id"]
    SqlTelemetryRepository(test_engine).log_metrics([
        NetworkMetric(session_id=session_id, sentence_index=0, response_time_seconds=0.5),
        NetworkMetric(session_id=session_id, sentence_index=1, response_time_seconds=1.5),
        NetworkMetric(session_id=session_id, sentence_index=2, response_time_seconds=1.0, status="FAILED"),
    ])
    body = client.get("/api/analytics/metrics?days=7").json()
    assert body["total_calls"] == 3
    assert body["avg_latency_ms"] == 1000.0 and body["max_latency_ms"] == 1500.0
    assert body["p95_latency_ms"] == 1500.0
    assert body["success_rate"] == pytest.approx(66.7)
    assert body["words_per_minute"] == 150.0


def test_metrics_empty(client: TestClient) -> None:
    body = client.get("/api/analytics/metrics").json()
    assert body["total_calls"] == 0 and body["words_per_minute"] == 0.0
