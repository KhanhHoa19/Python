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

ROUTE_MODULES = ["books", "player", "analytics", "voices", "notes", "settings", "export"]


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
        for module in ROUTE_MODULES:
            stack.enter_context(patch(f"src.api.routes.{module}.get_db_engine", return_value=test_engine))
        for target in (
            "src.core.player.audio_service.TTSFactory",
            "src.api.routes.voices.TTSFactory",
            "src.api.routes.settings.TTSFactory",
            "src.api.routes.health.TTSFactory",
        ):
            stack.enter_context(patch(target)).create_provider.return_value = provider
        with TestClient(create_app()) as test_client:
            yield test_client
    get_settings.cache_clear()


def add_book(engine: Engine, texts: list[str] | None = None) -> int:
    texts = texts or ["Xin chào các bạn.", "Đây là câu thứ hai."]
    sentences = [
        BookSentence(
            id=None, book_id=0, chapter_index=1, sentence_index=i, text_content=t,
            word_count=len(t.split()), content_hash=f"{i:064d}",
        )
        for i, t in enumerate(texts)
    ]
    book = Book(
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


def test_settings_defaults_and_update(client: TestClient) -> None:
    body = client.get("/api/settings").json()
    assert body["prefetch_count"] == 2 and body["daily_char_limit"] == 0 and body["provider"] == "mock"

    new = {"prefetch_count": 3, "default_speed": 1.25, "default_voice": "mock-vi-male", "daily_char_limit": 1000}
    updated = client.put("/api/settings", json=new).json()
    assert updated["prefetch_count"] == 3 and updated["default_voice"] == "mock-vi-male"
    assert client.get("/api/settings").json()["daily_char_limit"] == 1000


def test_settings_rejects_invalid_values(client: TestClient) -> None:
    bad = {"prefetch_count": 9, "default_speed": 1.0, "default_voice": "v", "daily_char_limit": 0}
    assert client.put("/api/settings", json=bad).status_code == 400


def test_daily_limit_blocks_new_synthesis_but_not_cached(client: TestClient, test_engine: Engine) -> None:
    book_id = add_book(test_engine, ["Câu một.", "Câu hai dài hơn nhiều."])
    settings = {"prefetch_count": 2, "default_speed": 1.0, "default_voice": "mock-vi-female", "daily_char_limit": 10}
    client.put("/api/settings", json=settings)

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
