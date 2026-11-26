"""HTTP client for the Audiobook TTS backend. The only module that talks to the network."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

import config


class ApiError(Exception):
    """Backend or network failure. `status` is 0 when the server could not be reached."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message

    @property
    def is_connection_error(self) -> bool:
        return self.status == 0

    @property
    def is_quota_error(self) -> bool:
        return self.status == 429


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
        if isinstance(body, dict) and body.get("error"):
            return str(body["error"])
    except ValueError:
        pass
    return f"HTTP {response.status_code}"


class ApiClient:
    """Thin typed wrapper over the REST API. Methods return decoded JSON (dict/list) or bytes."""

    def __init__(self, base_url: str | None = None, transport: httpx.BaseTransport | None = None):
        self._http = httpx.Client(
            base_url=(base_url or config.API_BASE_URL),
            timeout=config.REQUEST_TIMEOUT_SECONDS,
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    # -- plumbing -----------------------------------------------------------------

    def _request(self, method: str, path: str, *, timeout: float | None = None, **kwargs: Any) -> httpx.Response:
        try:
            response = self._http.request(method, path, timeout=timeout or self._http.timeout, **kwargs)
        except httpx.TimeoutException as exc:
            raise ApiError(0, "Máy chủ phản hồi quá chậm.") from exc
        except httpx.HTTPError as exc:
            raise ApiError(0, "Không kết nối được máy chủ.") from exc
        if response.status_code >= 400:
            raise ApiError(response.status_code, _error_message(response))
        return response

    def _json(self, method: str, path: str, **kwargs: Any) -> Any:
        return self._request(method, path, **kwargs).json()

    # -- health / settings -----------------------------------------------------------

    def health(self) -> dict[str, Any]:
        return self._json("GET", "/api/health")

    def network_health(self) -> dict[str, Any]:
        return self._json("GET", "/api/health/network", timeout=30)

    def verify_tts(self) -> dict[str, Any]:
        return self._json("POST", "/api/tts/verify", timeout=config.AUDIO_TIMEOUT_SECONDS)

    def get_settings(self) -> dict[str, Any]:
        return self._json("GET", "/api/settings")

    def update_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        return self._json("PUT", "/api/settings", json=settings)

    # -- books -------------------------------------------------------------------

    def list_books(self) -> list[dict[str, Any]]:
        return self._json("GET", "/api/books", params={"limit": 500})

    def delete_book(self, book_id: int) -> None:
        self._request("DELETE", f"/api/books/{book_id}")

    def ingest_book(self, path: str | Path, title: str = "", author: str = "") -> dict[str, Any]:
        file_path = Path(path)
        data = {k: v for k, v in (("title", title), ("author", author)) if v}
        with file_path.open("rb") as handle:
            return self._json(
                "POST", "/api/books/ingest", data=data, files={"file": (file_path.name, handle)},
                timeout=120,
            )

    def get_sentences(self, book_id: int) -> list[dict[str, Any]]:
        return self._json("GET", f"/api/books/{book_id}/sentences")["sentences"]

    # -- player ------------------------------------------------------------------

    def get_bookmark(self, book_id: int) -> dict[str, Any]:
        return self._json("GET", f"/api/bookmarks/{book_id}")

    def save_bookmark(self, book_id: int, chapter: int, sentence_index: int, percentage: float) -> None:
        self._request("POST", "/api/bookmarks", json={
            "book_id": book_id, "current_chapter": chapter,
            "current_sentence_index": sentence_index, "completion_percentage": percentage,
        })

    def record_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._json("POST", "/api/sessions", json=payload)

    def fetch_audio(self, book_id: int, sentence_index: int, speed: float = 1.0,
                    voice: str | None = None) -> tuple[bytes, str]:
        """Return (audio_bytes, extension) for one sentence."""
        params: dict[str, Any] = {"speed": speed}
        if voice:
            params["voice"] = voice
        response = self._request(
            "GET", f"/api/audio/{book_id}/{sentence_index}", params=params,
            timeout=config.AUDIO_TIMEOUT_SECONDS,
        )
        return response.content, _extension(response)

    # -- voices ------------------------------------------------------------------

    def list_voices(self) -> dict[str, Any]:
        return self._json("GET", "/api/voices", timeout=30)

    def clone_voice(self, sample_path: str | Path, name: str, language: str, gender: str | None,
                    consent: bool) -> dict[str, Any]:
        path = Path(sample_path)
        data: dict[str, Any] = {"name": name, "language": language, "consent": "true" if consent else "false"}
        if gender:
            data["gender"] = gender
        with path.open("rb") as handle:
            return self._json(
                "POST", "/api/voices/clone", data=data, files={"sample": (path.name, handle)}, timeout=180,
            )

    def delete_voice(self, voice_id: str) -> None:
        self._request("DELETE", f"/api/voices/{voice_id}")

    def preview_voice(self, voice_id: str) -> tuple[bytes, str]:
        response = self._request("GET", f"/api/voices/{voice_id}/preview", timeout=config.AUDIO_TIMEOUT_SECONDS)
        return response.content, _extension(response)

    # -- notes -------------------------------------------------------------------

    def list_notes(self, book_id: int | None = None) -> list[dict[str, Any]]:
        params = {"book_id": book_id} if book_id is not None else None
        return self._json("GET", "/api/notes", params=params)

    def create_note(self, book_id: int, sentence_index: int, start: int, end: int, text: str) -> dict[str, Any]:
        return self._json("POST", "/api/notes", json={
            "book_id": book_id, "sentence_index": sentence_index,
            "start_offset": start, "end_offset": end, "note_text": text,
        })

    def update_note(self, note_id: int, text: str) -> dict[str, Any]:
        return self._json("PATCH", f"/api/notes/{note_id}", json={"note_text": text})

    def delete_note(self, note_id: int) -> None:
        self._request("DELETE", f"/api/notes/{note_id}")

    def note_audio(self, note_id: int, speed: float = 1.0) -> tuple[bytes, str]:
        response = self._request(
            "GET", f"/api/notes/{note_id}/audio", params={"speed": speed}, timeout=config.AUDIO_TIMEOUT_SECONDS,
        )
        return response.content, _extension(response)

    # -- export ------------------------------------------------------------------

    def export_estimate(self, book_id: int, from_index: int = 0, to_index: int | None = None,
                        voice: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"from_index": from_index}
        if to_index is not None:
            params["to_index"] = to_index
        if voice:
            params["voice"] = voice
        return self._json("GET", f"/api/books/{book_id}/export/estimate", params=params, timeout=60)

    def start_export(self, book_id: int, from_index: int = 0, to_index: int | None = None,
                     voice: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"from_index": from_index}
        if to_index is not None:
            body["to_index"] = to_index
        if voice:
            body["voice"] = voice
        return self._json("POST", f"/api/books/{book_id}/export", json=body)

    def export_status(self, job_id: str) -> dict[str, Any]:
        return self._json("GET", f"/api/exports/{job_id}")

    def download_export(self, job_id: str, target: str | Path) -> None:
        response = self._request("GET", f"/api/exports/{job_id}/file", timeout=300)
        Path(target).write_bytes(response.content)

    # -- analytics ---------------------------------------------------------------

    def analytics_daily(self, days: int) -> list[dict[str, Any]]:
        return self._json("GET", "/api/analytics/daily", params={"days": days})

    def analytics_metrics(self, days: int) -> dict[str, Any]:
        return self._json("GET", "/api/analytics/metrics", params={"days": days})


def _extension(response: httpx.Response) -> str:
    content_type = response.headers.get("content-type", "")
    if "wav" in content_type:
        return "wav"
    if "ogg" in content_type:
        return "ogg"
    return "mp3"
