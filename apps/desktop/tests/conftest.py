"""Shared fakes for desktop tests (no Tk, no sound card, no network)."""

from __future__ import annotations

import io
import sys
import threading
import time
import wave
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_config_dir(tmp_path, monkeypatch):
    """Tests must never read or write the user's real saved appearance."""
    monkeypatch.setenv("AUDIOBOOK_TTS_CONFIG_DIR", str(tmp_path / "config"))


class FakeOutput:
    """Pretends to play each sound for `duration` seconds; records what was played."""

    def __init__(self, duration: float = 0.03):
        self.duration = duration
        self.played: list[bytes] = []
        self.stops = 0
        self.paused = False
        self.volume = 1.0
        self.volume_history: list[float] = []
        self._busy_until = 0.0
        self._lock = threading.Lock()

    def play(self, data: bytes, ext: str) -> float:
        with self._lock:
            self.played.append(data)
            self._busy_until = time.monotonic() + self.duration
        return self.duration

    # -- background sound (a second channel) --------------------------------------------------------
    ambient: dict | None = None  # {"data", "volume", "playing"} of the sound loaded now, or None

    def play_ambient(self, data: bytes, ext: str, volume: float) -> None:
        self.ambient = {"data": data, "volume": volume, "playing": True}

    def set_ambient_volume(self, volume: float) -> None:
        if self.ambient:
            self.ambient["volume"] = volume

    def pause_ambient(self) -> None:
        if self.ambient:
            self.ambient["playing"] = False

    def resume_ambient(self) -> None:
        if self.ambient:
            self.ambient["playing"] = True

    def stop_ambient(self) -> None:
        self.ambient = None

    def is_busy(self) -> bool:
        with self._lock:
            return self.paused or time.monotonic() < self._busy_until

    def set_volume(self, volume: float) -> None:
        with self._lock:
            self.volume = volume
            self.volume_history.append(volume)

    def pause(self) -> None:
        with self._lock:
            self.paused = True

    def resume(self) -> None:
        with self._lock:
            self.paused = False
            self._busy_until = time.monotonic() + self.duration

    def stop(self) -> None:
        with self._lock:
            self.stops += 1
            self.paused = False
            self._busy_until = 0.0

    def close(self) -> None:
        pass


@pytest.fixture
def output() -> FakeOutput:
    return FakeOutput()


def wait_for(condition, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


BACKEND_DIR = Path(__file__).resolve().parents[3] / "backend"


def make_wav(seconds: float) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * int(seconds * 8000))
    return buf.getvalue()


@pytest.fixture
def backend(tmp_path, monkeypatch):
    """A fresh in-process backend: temp SQLite DB, mock TTS provider, temp storage.

    Skips the test when the backend or its dependencies are not available.
    """
    pytest.importorskip("fastapi")
    pytest.importorskip("sqlalchemy")
    if not (BACKEND_DIR / "src").is_dir():
        pytest.skip("backend not found next to apps/")
    for key, value in {
        "DB_USE_SQLITE": "true", "SQLITE_PATH": str(tmp_path / "db.sqlite"), "TTS_PROVIDER": "mock",
        "AUDIO_CACHE_DIR": str(tmp_path / "cache"), "EXPORT_DIR": str(tmp_path / "exports"),
        "VOICE_SAMPLES_DIR": str(tmp_path / "samples"), "TESTING": "false", "MOCK_TTS": "false",
        "ADMIN_USERNAME": "admin", "ADMIN_PASSWORD": "admin-pass-123", "JWT_SECRET": "desktop-test-secret-" * 3,
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.syspath_prepend(str(BACKEND_DIR))
    for name in [m for m in sys.modules if m == "src" or m.startswith("src.")]:
        del sys.modules[name]  # backend modules must see the env above, not a previous import
    from src.api.app import create_app
    from src.core.config import get_settings
    from src.core.storage import db
    from src.core.storage.migrations import run_migrations

    get_settings.cache_clear()
    db._ENGINE = None
    run_migrations(db.get_db_engine())
    yield create_app()
    get_settings.cache_clear()
    db._ENGINE = None


@pytest.fixture
def api(backend):
    from fastapi.testclient import TestClient

    from api_client import ApiClient

    client = ApiClient(base_url="http://backend")
    client._http = TestClient(backend, base_url="http://backend")
    # Every endpoint needs an account: register one and sign in, as the desktop app does.
    signed_in = client.register("tester", "correct horse", "Người Thử")
    client.set_token(signed_in["access_token"])
    return client


@pytest.fixture
def admin_api(backend):
    """A second client on the same backend, signed in as the administrator."""
    from fastapi.testclient import TestClient

    from api_client import ApiClient

    client = ApiClient(base_url="http://backend")
    client._http = TestClient(backend, base_url="http://backend")
    client.set_token(client.login("admin", "admin-pass-123")["access_token"])
    return client


@pytest.fixture
def book(api, tmp_path) -> dict:
    sample = tmp_path / "bai_hoc.txt"
    sample.write_text("Xin chào các bạn. Đây là câu thứ hai. Và đây là câu thứ ba.", encoding="utf-8")
    return api.ingest_book(sample, title="Bài học")
