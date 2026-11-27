"""HeyGen provider against a fake HTTP server (no network, no real API key)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from src.core.config import get_settings
from src.core.tts.base import RateLimitError, TTSProviderError
from src.core.tts.factory import TTSFactory
from src.core.tts.heygen_adapter import HeyGenProvider, RateLimiter

AUDIO_URL = "https://files.example.test/tts/abc.mp3"
SECRET = "sk_test_secret_value"


@pytest.fixture(autouse=True)
def heygen_env(monkeypatch):
    """Known settings regardless of the developer's real .env."""
    for key, value in {
        "HEYGEN_MODEL": "heygen-voice-1", "HEYGEN_LANGUAGE": "vi", "HEYGEN_AUDIO_FORMAT": "mp3",
        "HEYGEN_API_KEY": "", "HEYGEN_DEFAULT_VOICE": "",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class Server:
    """Records every request and answers with `handler`."""

    def __init__(self, handler: Callable[[httpx.Request], httpx.Response]):
        self.requests: list[httpx.Request] = []
        self._handler = handler

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._handler(request)


def make(handler, *, api_key: str | None = SECRET, voice: str | None = "voice-1", rpm: int = 1000):
    server = Server(handler)
    sleeps: list[float] = []
    clock = {"now": 0.0}

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock["now"] += seconds  # fake time passes, so waiting is instant and deterministic

    provider = HeyGenProvider(
        default_voice=voice,
        api_key=api_key,
        client=httpx.Client(transport=httpx.MockTransport(server)),
        limiter=RateLimiter(rpm, clock=lambda: clock["now"], sleep=fake_sleep),
        sleep=fake_sleep,
    )
    return provider, server, sleeps


def tts_ok(request: httpx.Request) -> httpx.Response:
    if request.url.host == "api.heygen.com":
        return httpx.Response(200, json={"data": {"audio_url": AUDIO_URL, "duration": 2.5}})
    return httpx.Response(200, content=b"ID3-audio-bytes")


def body(request: httpx.Request) -> dict:
    return json.loads(request.content)


# ---------------------------------------------------------------- synthesize


def test_synthesize_sends_expected_request_and_downloads_audio() -> None:
    provider, server, _ = make(tts_ok)
    result = provider.synthesize("Xin chào các bạn.")

    api_call, download = server.requests
    assert api_call.method == "POST" and api_call.url.path == "/v3/models/audio/tts"
    assert api_call.headers["x-api-key"] == SECRET
    assert body(api_call) == {
        "model": "heygen-voice-1", "voice_id": "voice-1", "text": "Xin chào các bạn.",
        "language": "vi", "output_format": {"encoding": "mp3"},
    }
    assert str(download.url) == AUDIO_URL
    assert "x-api-key" not in download.headers  # the key must never reach the file host
    assert (result.audio_bytes, result.audio_format, result.duration_seconds) == (b"ID3-audio-bytes", "mp3", 2.5)


def test_speed_is_sent_only_when_not_default() -> None:
    provider, server, _ = make(tts_ok)
    provider.synthesize("a", speed=1.25)
    provider.synthesize("b", speed=1.0)
    assert body(server.requests[0])["speed"] == 1.25
    assert "speed" not in body(server.requests[2])


def test_wav_format_requests_no_output_format_and_detects_extension(monkeypatch) -> None:
    monkeypatch.setenv("HEYGEN_AUDIO_FORMAT", "wav")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.heygen.com":
            return httpx.Response(200, json={"data": {"audio_url": "https://files.example.test/x.wav", "duration": 1}})
        return httpx.Response(200, content=b"RIFFxxxx")

    provider, server, _ = make(handler)
    result = provider.synthesize("Câu thử.")
    assert "output_format" not in body(server.requests[0]) and result.audio_format == "wav"


def test_explicit_voice_overrides_default() -> None:
    provider, server, _ = make(tts_ok)
    provider.synthesize("x", voice="other-voice")
    assert body(server.requests[0])["voice_id"] == "other-voice"


def test_empty_text_and_missing_key_fail_without_calling_the_api() -> None:
    provider, server, _ = make(tts_ok)
    with pytest.raises(TTSProviderError, match="empty"):
        provider.synthesize("   ")
    no_key, no_key_server, _ = make(tts_ok, api_key="")
    with pytest.raises(TTSProviderError, match="HEYGEN_API_KEY"):
        no_key.synthesize("x")
    assert server.requests == [] and no_key_server.requests == []


def test_unauthorised_error_does_not_leak_the_key() -> None:
    provider, _, _ = make(lambda r: httpx.Response(401, json={"error": {"code": "unauthorized", "message": "bad"}}))
    with pytest.raises(TTSProviderError) as info:
        provider.synthesize("x")
    assert "401" in str(info.value) and SECRET not in str(info.value)


def test_api_error_message_is_surfaced() -> None:
    err = {"error": {"code": "invalid_parameter", "message": "Unsupported language code"}}
    provider, _, _ = make(lambda r: httpx.Response(400, json=err))
    with pytest.raises(TTSProviderError, match="Unsupported language code"):
        provider.synthesize("x")


def test_non_https_audio_url_is_rejected() -> None:
    provider, _, _ = make(lambda r: httpx.Response(200, json={"data": {"audio_url": "http://evil.test/a.mp3", "duration": 1}}))
    with pytest.raises(TTSProviderError, match="non-HTTPS"):
        provider.synthesize("x")


def test_missing_audio_url_and_failed_download() -> None:
    provider, _, _ = make(lambda r: httpx.Response(200, json={"data": {"duration": 1}}))
    with pytest.raises(TTSProviderError, match="audio_url"):
        provider.synthesize("x")

    def handler(request: httpx.Request) -> httpx.Response:
        return tts_ok(request) if request.url.host == "api.heygen.com" else httpx.Response(403)

    provider, server, sleeps = make(handler)
    with pytest.raises(TTSProviderError, match="download"):
        provider.synthesize("x")
    assert len(server.requests) == 3 and sleeps == [1.0]  # one API call + download tried twice


# ---------------------------------------------------------------- retries and rate limiting


def test_transient_server_error_is_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host != "api.heygen.com":
            return httpx.Response(200, content=b"audio")
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, json={"error": {"code": "service_unavailable", "message": "busy"}})
        return httpx.Response(200, json={"data": {"audio_url": AUDIO_URL, "duration": 1}})

    provider, _, sleeps = make(handler)
    assert provider.synthesize("x").audio_bytes == b"audio"
    assert calls["n"] == 2 and sleeps == [2.0]


def test_rate_limit_honours_retry_after_then_gives_up() -> None:
    err = {"error": {"code": "rate_limit_exceeded", "message": "slow down"}}
    provider, server, sleeps = make(lambda r: httpx.Response(429, json=err, headers={"Retry-After": "7"}))
    with pytest.raises(RateLimitError, match="rate limit"):
        provider.synthesize("x")
    assert len(server.requests) == 3 and sleeps == [7.0, 7.0]


def test_connection_failure_becomes_provider_error() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    provider, _, _ = make(refuse)
    with pytest.raises(TTSProviderError, match="Could not reach HeyGen"):
        provider.synthesize("x")


class CountingLimiter(RateLimiter):
    def __init__(self) -> None:
        super().__init__(1000)
        self.waits = 0

    def wait(self) -> None:
        self.waits += 1


def test_every_api_call_goes_through_the_limiter_but_the_file_download_does_not() -> None:
    limiter = CountingLimiter()
    server = Server(tts_ok)
    provider = HeyGenProvider("voice-1", api_key=SECRET, limiter=limiter, sleep=lambda s: None,
                              client=httpx.Client(transport=httpx.MockTransport(server)))
    provider.synthesize("x")
    assert len(server.requests) == 2 and limiter.waits == 1  # API call counted, download not

    calls = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503) if calls["n"] < 3 else httpx.Response(200, json={"data": {}})

    retrying = CountingLimiter()
    provider2 = HeyGenProvider("voice-1", api_key=SECRET, limiter=retrying, sleep=lambda s: None,
                               client=httpx.Client(transport=httpx.MockTransport(flaky)))
    with pytest.raises(TTSProviderError):
        provider2.synthesize("x")  # fails on the missing audio_url, after 3 attempts
    assert retrying.waits == 3  # every retry is also limited


def test_requests_beyond_the_per_minute_budget_wait_instead_of_failing() -> None:
    provider, server, sleeps = make(tts_ok, rpm=2)
    for _ in range(3):
        provider.synthesize("x")
    assert len(server.requests) == 6 and sleeps  # the 3rd API call had to wait for the window


def test_rate_limiter_blocks_when_the_window_is_full() -> None:
    now = {"t": 0.0}
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now["t"] += seconds

    limiter = RateLimiter(3, period=60.0, clock=lambda: now["t"], sleep=fake_sleep)
    for _ in range(3):
        limiter.wait()
    assert sleeps == []
    now["t"] = 10.0
    limiter.wait()  # 4th call must wait until the first one leaves the window (t=60)
    assert sleeps == [50.0] and now["t"] == 60.0


def test_rate_limiter_is_shared_by_providers_via_the_factory(monkeypatch) -> None:
    monkeypatch.setenv("TTS_PROVIDER", "heygen")
    get_settings.cache_clear()
    first = TTSFactory.create_provider()
    second = TTSFactory.create_provider()
    assert isinstance(first, HeyGenProvider) and first._limiter is second._limiter
    assert first._client is second._client


# ---------------------------------------------------------------- voices


def voices_handler(pages: dict[tuple[str, str | None], dict]):
    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        key = (params["type"], params.get("token"))
        if key not in pages:
            return httpx.Response(400, json={"error": {"code": "invalid_parameter", "message": "Unsupported language code"}})
        return httpx.Response(200, json=pages[key])

    return handler


def test_list_voices_returns_private_then_public_and_skips_inactive() -> None:
    pages = {
        ("private", None): {"data": [
            {"voice_id": "p1", "name": "hayami", "language": "vi", "status": "ACTIVE"},
            {"voice_id": "p2", "name": "broken", "language": "vi", "status": "FAILED"},
            {"voice_id": "p3", "name": "waiting", "status": "PENDING"},
        ], "has_more": True, "next_token": "t2"},
        ("private", "t2"): {"data": [{"voice_id": "p4", "name": "second page", "language": "vi", "status": "ACTIVE"}], "has_more": False},
        ("public", None): {"data": [{"voice_id": "u1", "name": "Public vi", "language": "vi", "gender": "female"}], "has_more": False},
    }
    provider, server, _ = make(voices_handler(pages))
    voices = provider.list_voices()

    assert [v.voice_id for v in voices] == ["p1", "p4", "u1"]
    assert voices[0].style == "giọng của bạn (HeyGen)" and voices[2].gender == "female"
    public_call = next(r for r in server.requests if r.url.params.get("type") == "public")
    assert public_call.url.params["language"] == "vi"


def test_public_listing_failure_does_not_hide_workspace_voices() -> None:
    pages = {("private", None): {"data": [{"voice_id": "p1", "name": "hayami", "status": "ACTIVE"}], "has_more": False}}
    provider, _, _ = make(voices_handler(pages))
    assert [v.voice_id for v in provider.list_voices()] == ["p1"]  # public call got a 400 and was ignored


def test_private_listing_failure_is_reported() -> None:
    provider, _, _ = make(voices_handler({}))
    with pytest.raises(TTSProviderError, match="Unsupported language"):
        provider.list_voices()


def test_default_voice_falls_back_to_first_active_workspace_voice() -> None:
    pages = {
        ("private", None): {"data": [{"voice_id": "mine", "name": "hayami", "status": "ACTIVE"}], "has_more": False},
        ("public", None): {"data": [], "has_more": False},
    }
    provider, server, _ = make(voices_handler(pages), voice=None)
    assert provider.default_voice == "mine"
    _ = provider.default_voice  # second access is cached
    assert len(server.requests) == 2

    empty, _, _ = make(voices_handler({("private", None): {"data": [], "has_more": False},
                                       ("public", None): {"data": [], "has_more": False}}), voice=None)
    with pytest.raises(TTSProviderError, match="No HeyGen voice"):
        _ = empty.default_voice


# ---------------------------------------------------------------- cloning


def sample(tmp_path: Path, name: str = "giong.wav") -> Path:
    path = tmp_path / name
    path.write_bytes(b"RIFF....WAVEdata")
    return path


def clone_handler(statuses: list[dict]):
    states = iter(statuses)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v3/assets":
            return httpx.Response(200, json={"data": {"asset_id": "asset-1", "url": "https://x/y"}})
        if path == "/v3/models/audio/voices" and request.method == "POST":
            return httpx.Response(202, json={"data": {"voice_id": "clone-1"}})
        if path == "/v3/models/audio/voices/clone-1" and request.method == "GET":
            return httpx.Response(200, json={"data": next(states)})
        return httpx.Response(404, json={"error": {"code": "not_found", "message": path}})

    return handler


def test_clone_uploads_creates_and_waits_until_active(tmp_path: Path) -> None:
    provider, server, sleeps = make(clone_handler([{"status": "PENDING"}, {"status": "PENDING"}, {"status": "ACTIVE"}]))
    voice_id = provider.clone_voice(str(sample(tmp_path)), "T" * 100, "vi")

    assert voice_id == "clone-1"
    upload, create, *polls = server.requests
    assert upload.url.path == "/v3/assets" and b'filename="giong.wav"' in upload.content
    assert upload.headers["content-type"].startswith("multipart/form-data")
    assert body(create) == {
        "mode": "instant", "name": "T" * 64, "language": "vi",
        "audio": [{"type": "asset_id", "asset_id": "asset-1"}],
    }
    assert create.headers["idempotency-key"]
    assert len(polls) == 3 and sleeps == [2.0, 2.0]


def test_clone_failure_reports_the_reason(tmp_path: Path) -> None:
    provider, _, _ = make(clone_handler([{"status": "FAILED", "failure_reason": "INVALID_AUDIO"}]))
    with pytest.raises(TTSProviderError, match="INVALID_AUDIO"):
        provider.clone_voice(str(sample(tmp_path)), "x", "vi")


def test_clone_gives_up_when_the_voice_never_becomes_active(tmp_path: Path) -> None:
    provider, _, sleeps = make(clone_handler([{"status": "PENDING"}] * 200))
    with pytest.raises(TTSProviderError, match="still processing"):
        provider.clone_voice(str(sample(tmp_path)), "x", "vi")
    assert len(sleeps) == 90


def test_clone_rejects_unsupported_sample_formats_before_any_request(tmp_path: Path) -> None:
    provider, server, _ = make(clone_handler([]))
    with pytest.raises(TTSProviderError, match="WAV or MP3"):
        provider.clone_voice(str(sample(tmp_path, "giong.m4a")), "x", "vi")
    assert server.requests == []


def test_delete_voice_tolerates_already_deleted_voices() -> None:
    provider, server, _ = make(lambda r: httpx.Response(204))
    provider.delete_voice("v1")
    assert server.requests[0].method == "DELETE" and server.requests[0].url.path == "/v3/models/audio/voices/v1"

    gone, _, _ = make(lambda r: httpx.Response(404, json={"error": {"code": "voice_not_found", "message": "Voice not found."}}))
    gone.delete_voice("v1")  # no exception

    broken, _, _ = make(lambda r: httpx.Response(400, json={"error": {"code": "resource_busy", "message": "no"}}))
    with pytest.raises(TTSProviderError):
        broken.delete_voice("v1")


def test_capabilities() -> None:
    provider, _, _ = make(tts_ok)
    assert provider.provider_name == "heygen" and provider.supports_cloning
    assert provider.clone_sample_seconds == (5.0, 180.0)


# ---------------------------------------------------------------- configuration


def test_heygen_default_voice_comes_from_its_own_setting(monkeypatch) -> None:
    monkeypatch.setenv("TTS_PROVIDER", "heygen")
    monkeypatch.setenv("TTS_DEFAULT_VOICE", "en-US-ChristopherNeural")
    monkeypatch.setenv("HEYGEN_DEFAULT_VOICE", "my-voice-id")
    get_settings.cache_clear()
    assert get_settings().effective_default_voice == "my-voice-id"
    assert TTSFactory.create_provider()._configured_voice == "my-voice-id"

    monkeypatch.setenv("TTS_PROVIDER", "edge-tts")
    get_settings.cache_clear()
    assert get_settings().effective_default_voice == "en-US-ChristopherNeural"
