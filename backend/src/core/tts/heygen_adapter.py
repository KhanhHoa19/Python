"""HeyGen Voice provider: text-to-speech with a chosen voice and instant voice cloning.

API (https://developers.heygen.com):
- POST /v3/models/audio/tts           -> {"data": {"audio_url", "duration"}}, then the file is downloaded
- GET  /v3/models/audio/voices        -> voices of the workspace (type=private) or the public library
- POST /v3/assets                     -> upload a recording, returns an asset_id
- POST /v3/models/audio/voices        -> instant clone (mode=instant), async; poll GET .../voices/{id}
- DELETE /v3/models/audio/voices/{id}

HeyGen allows 30 requests per minute per workspace member, so every call goes through a
process-wide rate limiter (the factory creates a new provider per request, so the limiter and the
HTTP client are module-level singletons). The API key is sent only to api.heygen.com, never to
the file host that serves `audio_url`, and never appears in logs or error messages.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from src.core.config import get_settings
from src.core.tts.base import (
    AudioSynthesisResult,
    RateLimitError,
    TTSProvider,
    TTSProviderError,
    VoiceInfo,
)

logger = logging.getLogger(__name__)

API_BASE = "https://api.heygen.com"
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 3
_MAX_RETRY_WAIT_SECONDS = 30.0
_CLONE_POLL_SECONDS = 2.0
_CLONE_TIMEOUT_SECONDS = 180.0
_SAMPLE_EXTENSIONS = {".wav", ".mp3"}  # what POST /v3/assets accepts for audio
_PAGE_LIMIT = 50
_MAX_PAGES = 20


class RateLimiter:
    """Sliding-window limiter: at most `max_calls` per `period` seconds, shared by all threads."""

    def __init__(
        self,
        max_calls: int,
        period: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.max_calls = max(1, max_calls)
        self.period = period
        self._clock = clock
        self._sleep = sleep
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def wait(self) -> None:
        """Block until a request may be sent, then record it."""
        while True:
            with self._lock:
                now = self._clock()
                while self._calls and now - self._calls[0] >= self.period:
                    self._calls.popleft()
                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return
                delay = self.period - (now - self._calls[0])
            self._sleep(max(delay, 0.01))  # sleep outside the lock so other threads can queue


_shared_lock = threading.Lock()
_shared_limiter: RateLimiter | None = None
_shared_client: httpx.Client | None = None


def _get_shared_limiter(max_calls: int) -> RateLimiter:
    global _shared_limiter
    with _shared_lock:
        if _shared_limiter is None or _shared_limiter.max_calls != max(1, max_calls):
            _shared_limiter = RateLimiter(max_calls)
        return _shared_limiter


def _get_shared_client() -> httpx.Client:
    global _shared_client
    with _shared_lock:
        if _shared_client is None:
            _shared_client = httpx.Client(timeout=httpx.Timeout(90.0, connect=15.0))
        return _shared_client


def _error_message(response: httpx.Response) -> str:
    """Readable message from HeyGen's {"error": {...}} body (never includes request headers)."""
    try:
        error = response.json().get("error", {})
        if isinstance(error, dict) and error.get("message"):
            return f"{error['message']} ({response.status_code}, {error.get('code', 'error')})"
    except ValueError:
        pass
    return f"HTTP {response.status_code}"


class HeyGenProvider(TTSProvider):
    """Speech synthesis and voice cloning through the HeyGen Voice API."""

    def __init__(
        self,
        default_voice: str | None = None,
        *,
        api_key: str | None = None,
        client: httpx.Client | None = None,
        limiter: RateLimiter | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        cfg = get_settings()
        self._api_key = api_key if api_key is not None else cfg.heygen_api_key
        self._model = cfg.heygen_model
        self._language = cfg.heygen_language
        self._audio_format = cfg.heygen_audio_format.lower()
        self._configured_voice = default_voice or cfg.heygen_default_voice
        self._resolved_voice: str | None = None
        self._client = client or _get_shared_client()
        self._limiter = limiter or _get_shared_limiter(cfg.heygen_requests_per_minute)
        self._sleep = sleep

    # ------------------------------------------------------------------ identity

    @property
    def provider_name(self) -> str:
        return "heygen"

    @property
    def default_voice(self) -> str:
        """Configured voice, else the first ACTIVE voice of the workspace."""
        if self._configured_voice:
            return self._configured_voice
        if self._resolved_voice is None:
            voices = self.list_voices()
            if not voices:
                raise TTSProviderError("No HeyGen voice available: create a voice or set HEYGEN_DEFAULT_VOICE.")
            self._resolved_voice = voices[0].voice_id
        return self._resolved_voice

    @property
    def cache_namespace(self) -> str:
        return f"heygen:{self._model}"

    @property
    def supports_cloning(self) -> bool:
        return True

    @property
    def clone_sample_seconds(self) -> tuple[float, float]:
        # About one minute of clear speech clones best and HeyGen uses at most the first 3 minutes.
        return (5.0, 180.0)

    # ------------------------------------------------------------------ HTTP plumbing

    def _auth_headers(self) -> dict[str, str]:
        if not self._api_key:
            raise TTSProviderError("HEYGEN_API_KEY is not configured.")
        return {"X-Api-Key": self._api_key, "Accept": "application/json"}

    def _retry_wait(self, response: httpx.Response, attempt: int) -> float:
        header = response.headers.get("retry-after", "")
        try:
            return min(float(header), _MAX_RETRY_WAIT_SECONDS)
        except ValueError:
            return min(2.0**attempt, _MAX_RETRY_WAIT_SECONDS)

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Rate-limited call with retries on 429/5xx. Raises TTSProviderError / RateLimitError."""
        headers = {**self._auth_headers(), **kwargs.pop("headers", {})}
        response: httpx.Response | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            self._limiter.wait()
            try:
                response = self._client.request(method, f"{API_BASE}{path}", headers=headers, **kwargs)
            except httpx.TimeoutException as exc:
                if attempt == _MAX_ATTEMPTS:
                    raise TTSProviderError("HeyGen did not respond in time.") from exc
                self._sleep(min(2.0**attempt, _MAX_RETRY_WAIT_SECONDS))
                continue
            except httpx.HTTPError as exc:
                raise TTSProviderError(f"Could not reach HeyGen: {type(exc).__name__}") from exc
            if response.status_code in _RETRY_STATUSES and attempt < _MAX_ATTEMPTS:
                self._sleep(self._retry_wait(response, attempt))
                continue
            break

        assert response is not None
        if response.status_code == 429:
            raise RateLimitError(f"HeyGen rate limit reached: {_error_message(response)}")
        if response.status_code == 401:
            raise TTSProviderError("HeyGen rejected the API key (401).")
        if response.status_code >= 400:
            raise TTSProviderError(f"HeyGen error: {_error_message(response)}")
        return response

    def _json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        body = self._request(method, path, **kwargs).json()
        data = body.get("data", body) if isinstance(body, dict) else None
        if not isinstance(data, dict):
            raise TTSProviderError("Unexpected response from HeyGen.")
        return data

    def _download(self, url: str) -> bytes:
        """Fetch the generated file. No API key is sent to this host."""
        if urlparse(url).scheme != "https":
            raise TTSProviderError("HeyGen returned a non-HTTPS audio URL.")
        last_error: Exception | None = None
        for attempt in (1, 2):
            try:
                response = self._client.get(url)
                if response.status_code == 200 and response.content:
                    return response.content
                last_error = TTSProviderError(f"Audio download failed (HTTP {response.status_code}).")
            except httpx.HTTPError as exc:
                last_error = exc
            if attempt == 1:
                self._sleep(1.0)
        raise TTSProviderError(f"Could not download the generated audio: {last_error}")

    # ------------------------------------------------------------------ synthesis

    def synthesize(self, text: str, voice: str | None = None, speed: float = 1.0) -> AudioSynthesisResult:
        if not text.strip():
            raise TTSProviderError("Cannot synthesize empty text.")
        started = time.perf_counter()
        body: dict[str, Any] = {
            "model": self._model,
            "voice_id": voice or self.default_voice,
            "text": text,
            "language": self._language,
        }
        if speed != 1.0:
            body["speed"] = speed
        if self._audio_format == "mp3":
            body["output_format"] = {"encoding": "mp3"}

        data = self._json("POST", "/v3/models/audio/tts", json=body)
        audio_url = data.get("audio_url")
        if not audio_url:
            raise TTSProviderError("HeyGen returned no audio_url.")
        audio = self._download(str(audio_url))

        extension = Path(urlparse(str(audio_url)).path).suffix.lstrip(".").lower()
        return AudioSynthesisResult(
            audio_bytes=audio,
            audio_format=extension if extension in ("mp3", "wav") else self._audio_format,
            duration_seconds=float(data.get("duration") or 0.0),
            response_time_seconds=time.perf_counter() - started,
        )

    # ------------------------------------------------------------------ voices

    def _list_page_set(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        voices: list[dict[str, Any]] = []
        token: str | None = None
        for _ in range(_MAX_PAGES):
            query = {**params, "limit": _PAGE_LIMIT, **({"token": token} if token else {})}
            body = self._request("GET", "/v3/models/audio/voices", params=query).json()
            voices.extend(body.get("data", []))
            token = body.get("next_token")
            if not body.get("has_more") or not token:
                break
        return voices

    def list_voices(self) -> list[VoiceInfo]:
        """The workspace's own voices first, then public voices in the configured language."""
        result: list[VoiceInfo] = []
        sources = (("private", {"type": "private"}), ("public", {"type": "public", "language": self._language}))
        for kind, params in sources:
            try:
                raw = self._list_page_set(params)
            except TTSProviderError:
                if kind == "private":
                    raise
                logger.warning("Could not list public HeyGen voices; showing workspace voices only.")
                continue
            for item in raw:
                if item.get("status", "ACTIVE") != "ACTIVE" or not item.get("voice_id"):
                    continue
                result.append(
                    VoiceInfo(
                        voice_id=item["voice_id"],
                        display_name=item.get("name") or item["voice_id"],
                        language=item.get("language") or self._language,
                        gender=item.get("gender"),
                        style="giọng của bạn (HeyGen)" if kind == "private" else "HeyGen",
                    )
                )
        return result

    def clone_voice(self, sample_path: str, name: str, language: str = "vi") -> str:
        """Upload a recording, create an instant voice and wait until it is ACTIVE."""
        path = Path(sample_path)
        if path.suffix.lower() not in _SAMPLE_EXTENSIONS:
            raise TTSProviderError("HeyGen accepts WAV or MP3 recordings for cloning.")

        with path.open("rb") as handle:
            upload = self._json("POST", "/v3/assets", files={"file": (path.name, handle)})
        asset_id = upload.get("asset_id")
        if not asset_id:
            raise TTSProviderError("HeyGen did not return an asset id for the recording.")

        created = self._json(
            "POST",
            "/v3/models/audio/voices",
            json={
                "mode": "instant",
                "name": name.strip()[:64],
                "language": language or self._language,
                "audio": [{"type": "asset_id", "asset_id": asset_id}],
            },
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
        voice_id = created.get("voice_id")
        if not voice_id:
            raise TTSProviderError("HeyGen did not return a voice id.")
        return self._wait_until_active(str(voice_id))

    def _wait_until_active(self, voice_id: str) -> str:
        for _ in range(int(_CLONE_TIMEOUT_SECONDS / _CLONE_POLL_SECONDS)):
            voice = self._json("GET", f"/v3/models/audio/voices/{voice_id}")
            status = voice.get("status")
            if status == "ACTIVE":
                return voice_id
            if status == "FAILED":
                raise TTSProviderError(
                    f"HeyGen could not create the voice ({voice.get('failure_reason', 'unknown reason')})."
                )
            self._sleep(_CLONE_POLL_SECONDS)
        raise TTSProviderError("HeyGen is still processing the voice. Try again in a few minutes.")

    def delete_voice(self, voice_id: str) -> None:
        try:
            self._request("DELETE", f"/v3/models/audio/voices/{voice_id}")
        except TTSProviderError as exc:
            if "voice_not_found" not in str(exc):  # already gone is fine
                raise
