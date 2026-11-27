"""HTTP client for the Audiobook TTS backend. The only module that talks to the network."""

from __future__ import annotations

from collections.abc import Callable
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
        self.token: str | None = None
        # Called (from whatever thread made the request) when the saved sign-in stops working.
        self.on_unauthorized: Callable[[], None] | None = None

    def set_token(self, token: str | None) -> None:
        """The sign-in sent with every request (None = signed out)."""
        self.token = token
        if token:
            self._http.headers["Authorization"] = f"Bearer {token}"
        else:
            self._http.headers.pop("Authorization", None)

    # -- accounts ------------------------------------------------------------------

    def login(self, username: str, password: str) -> dict[str, Any]:
        return self._json("POST", "/api/auth/login", json={"username": username, "password": password})

    def register(self, username: str, password: str, full_name: str = "") -> dict[str, Any]:
        return self._json("POST", "/api/auth/register",
                          json={"username": username, "password": password, "full_name": full_name})

    def demo_accounts(self) -> list[dict[str, Any]]:
        """Ready-made accounts of development mode; empty on a normal server."""
        return self._json("GET", "/api/auth/demo-accounts")

    def me(self) -> dict[str, Any]:
        return self._json("GET", "/api/auth/me")

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
            # A wrong password at sign-in is also a 401: only a rejected saved sign-in means "expired".
            if response.status_code == 401 and self.token and not path.startswith("/api/auth/") and self.on_unauthorized:
                self.on_unauthorized()
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

    @staticmethod
    def _filters(q: str = "", category: str | None = None, source: str | None = None,
                 status: str | None = None, sort: str | None = None) -> dict[str, Any]:
        params = {"q": q.strip(), "category": category, "source": source, "status": status, "sort": sort}
        return {k: v for k, v in params.items() if v}

    def list_books(self, q: str = "", category: str | None = None, source: str | None = None,
                   status: str | None = None, sort: str | None = None) -> list[dict[str, Any]]:
        """The caller's shelf (own books + public books they added), each with its `progress`. Filters combine."""
        params = {**self._filters(q, category, source, status, sort), "limit": 500}
        return self._json("GET", "/api/books", params=params)

    def shelf_counts(self, q: str = "", category: str | None = None, source: str | None = None) -> dict[str, int]:
        return self._json("GET", "/api/books/counts", params=self._filters(q, category, source))

    def explore_books(self, q: str = "", category: str | None = None, sort: str | None = None) -> list[dict[str, Any]]:
        """The public catalogue (Khám phá); `on_shelf` tells whether the caller already added a book."""
        return self._json("GET", "/api/books/explore", params={**self._filters(q, category, None, None, sort), "limit": 500})

    def list_categories(self) -> list[dict[str, Any]]:
        return self._json("GET", "/api/categories")

    def add_to_shelf(self, book_id: int) -> None:
        self._request("POST", f"/api/books/{book_id}/shelf")

    def remove_from_shelf(self, book_id: int) -> None:
        self._request("DELETE", f"/api/books/{book_id}/shelf")

    def set_favorite(self, book_id: int, is_favorite: bool) -> None:
        self._request("PUT", f"/api/books/{book_id}/favorite", json={"is_favorite": is_favorite})

    def set_read_status(self, book_id: int, status: str) -> None:
        """'completed' = đánh dấu đã nghe xong; 'unread' = nghe lại từ đầu."""
        self._request("PUT", f"/api/books/{book_id}/status", json={"status": status})

    def update_book(self, book_id: int, **changes: Any) -> dict[str, Any]:
        """Only the fields given change: `title=...`, `category_id=...` (None clears it)."""
        return self._json("PATCH", f"/api/books/{book_id}", json=changes)

    def rename_book(self, book_id: int, title: str) -> dict[str, Any]:
        return self.update_book(book_id, title=title)

    def replace_cover(self, book_id: int, path: str | Path) -> dict[str, Any]:
        file_path = Path(path)
        with file_path.open("rb") as handle:
            return self._json("PUT", f"/api/books/{book_id}/cover", files={"file": (file_path.name, handle)}, timeout=60)

    def cover_bytes(self, cover_url: str) -> bytes:
        """The image behind a book's `cover_url` (needs no token)."""
        return self._request("GET", cover_url).content

    def delete_book(self, book_id: int) -> None:
        self._request("DELETE", f"/api/books/{book_id}")

    def ingest_book(self, path: str | Path, title: str = "", author: str = "", category_id: int | None = None,
                    cover: str | Path | None = None, is_public: bool = False) -> dict[str, Any]:
        file_path = Path(path)
        data: dict[str, Any] = {k: v for k, v in (("title", title), ("author", author)) if v}
        if category_id is not None:
            data["category_id"] = str(category_id)
        if is_public:
            data["is_public"] = "true"
        with file_path.open("rb") as handle:
            files: dict[str, Any] = {"file": (file_path.name, handle)}
            if cover:
                cover_handle = Path(cover).open("rb")  # noqa: SIM115  (closed in the finally below)
                files["cover"] = (Path(cover).name, cover_handle)
            try:
                return self._json("POST", "/api/books/ingest", data=data, files=files, timeout=120)
            finally:
                if cover:
                    cover_handle.close()

    def get_sentences(self, book_id: int) -> list[dict[str, Any]]:
        return self._json("GET", f"/api/books/{book_id}/sentences")["sentences"]

    def get_chapters(self, book_id: int) -> list[dict[str, Any]]:
        return self._json("GET", f"/api/books/{book_id}/chapters")["chapters"]

    # -- player ------------------------------------------------------------------

    def get_bookmark(self, book_id: int) -> dict[str, Any]:
        return self._json("GET", f"/api/bookmarks/{book_id}")

    def save_bookmark(self, book_id: int, chapter: int, sentence_index: int, percentage: float,
                      voice: str | None = None) -> None:
        body: dict[str, Any] = {
            "book_id": book_id, "current_chapter": chapter,
            "current_sentence_index": sentence_index, "completion_percentage": percentage,
        }
        if voice:
            body["voice"] = voice  # remembered per book
        self._request("POST", "/api/bookmarks", json=body)

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

    def rename_voice(self, voice_id: str, display_name: str) -> dict[str, Any]:
        return self._json("PATCH", f"/api/voices/{voice_id}", json={"display_name": display_name})

    # -- admin (role=admin only) ------------------------------------------------

    def admin_books(self) -> list[dict[str, Any]]:
        return self._json("GET", "/api/admin/books")

    def set_book_public(self, book_id: int, is_public: bool) -> dict[str, Any]:
        return self._json("PUT", f"/api/admin/books/{book_id}/public", json={"is_public": is_public})

    def admin_categories(self) -> list[dict[str, Any]]:
        return self._json("GET", "/api/admin/categories")

    def create_category(self, name: str, icon: str, color: str) -> dict[str, Any]:
        return self._json("POST", "/api/admin/categories", json={"name": name, "icon": icon, "color": color})

    def update_category(self, category_id: int, name: str, icon: str, color: str) -> dict[str, Any]:
        return self._json("PUT", f"/api/admin/categories/{category_id}", json={"name": name, "icon": icon, "color": color})

    def delete_category(self, category_id: int) -> None:
        self._request("DELETE", f"/api/admin/categories/{category_id}")

    def admin_voices(self) -> dict[str, Any]:
        return self._json("GET", "/api/admin/voices")

    def set_voice_public(self, voice_id: str, is_public: bool) -> dict[str, Any]:
        return self._json("PUT", f"/api/admin/voices/{voice_id}/public", json={"is_public": is_public})

    def set_default_voice(self, voice_id: str) -> dict[str, Any]:
        return self._json("PUT", "/api/admin/default-voice", json={"voice_id": voice_id})

    def admin_users(self) -> list[dict[str, Any]]:
        return self._json("GET", "/api/admin/users")

    def preview_voice(self, voice_id: str) -> tuple[bytes, str]:
        response = self._request("GET", f"/api/voices/{voice_id}/preview", timeout=config.AUDIO_TIMEOUT_SECONDS)
        return response.content, _extension(response)

    # -- background sounds -------------------------------------------------------

    def list_ambient(self) -> list[dict[str, Any]]:
        return self._json("GET", "/api/ambient")

    def fetch_ambient(self, track_id: int) -> tuple[bytes, str]:
        """The sound's audio and its extension. The file route needs no token, but sending one does no harm."""
        response = self._request("GET", f"/api/ambient/{track_id}/audio", timeout=60)
        return response.content, _extension(response)

    def add_ambient(self, path: str | Path, name: str) -> dict[str, Any]:
        file_path = Path(path)
        with file_path.open("rb") as handle:
            return self._json("POST", "/api/admin/ambient", data={"name": name},
                              files={"file": (file_path.name, handle)}, timeout=120)

    def rename_ambient(self, track_id: int, name: str) -> dict[str, Any]:
        return self._json("PATCH", f"/api/admin/ambient/{track_id}", json={"name": name})

    def delete_ambient(self, track_id: int) -> None:
        self._request("DELETE", f"/api/admin/ambient/{track_id}")

    # -- notes -------------------------------------------------------------------

    def list_notes(self, book_id: int | None = None, emotion_tag: str | None = None) -> list[dict[str, Any]]:
        params = {k: v for k, v in (("book_id", book_id), ("emotion_tag", emotion_tag)) if v is not None}
        return self._json("GET", "/api/notes", params=params or None)

    def create_note(self, book_id: int, sentence_index: int, start: int | None = None, end: int | None = None,
                    text: str = "", emotion_tag: str | None = None, voice: str | None = None) -> dict[str, Any]:
        """A favourite quote. Without `start`/`end` it is the WHOLE sentence (the one-tap bookmark); saving the same
        passage twice returns the quote that already exists."""
        body: dict[str, Any] = {"book_id": book_id, "sentence_index": sentence_index, "note_text": text}
        if start is not None and end is not None:
            body.update(start_offset=start, end_offset=end)
        if emotion_tag:
            body["emotion_tag"] = emotion_tag
        if voice:
            body["voice"] = voice
        return self._json("POST", "/api/notes", json=body)

    def update_note(self, note_id: int, **changes: Any) -> dict[str, Any]:
        """`note_text=...` and/or `emotion_tag=...` (None removes the tag); only what is given changes."""
        return self._json("PATCH", f"/api/notes/{note_id}", json=changes)

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

    def cancel_export(self, job_id: str) -> dict[str, Any]:
        return self._json("DELETE", f"/api/exports/{job_id}")

    def download_export(self, job_id: str, target: str | Path) -> None:
        response = self._request("GET", f"/api/exports/{job_id}/file", timeout=300)
        Path(target).write_bytes(response.content)

    # -- analytics ---------------------------------------------------------------

    def analytics_daily(self, days: int) -> list[dict[str, Any]]:
        return self._json("GET", "/api/analytics/daily", params={"days": days})

    def analytics_voices(self, days: int) -> list[dict[str, Any]]:
        return self._json("GET", "/api/analytics/voices", params={"days": days})

    def analytics_metrics(self, days: int) -> dict[str, Any]:
        return self._json("GET", "/api/analytics/metrics", params={"days": days})


def _extension(response: httpx.Response) -> str:
    content_type = response.headers.get("content-type", "")
    if "wav" in content_type:
        return "wav"
    if "ogg" in content_type:
        return "ogg"
    return "mp3"
