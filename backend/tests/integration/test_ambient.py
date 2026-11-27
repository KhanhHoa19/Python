"""Background sounds: only admins manage the library, everyone can list and play it, each person chooses their own."""

from __future__ import annotations

import io
import wave
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from src.core.audio.ambient import ambient_dir
from tests.auth_helpers import make_user, sign_in, user_by_name
from tests.integration.test_accounts import app  # noqa: F401  (fixture)
from tests.integration.test_api_extended import provider  # noqa: F401

MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 2000


def _wav() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 800)
    return buffer.getvalue()


@pytest.fixture
def people(app: TestClient, test_engine: Engine, provider):  # noqa: F811
    with patch("src.api.routes.admin.TTSFactory") as factory:
        factory.create_provider.return_value = provider
        yield (
            sign_in(TestClient(app.app), test_engine, make_user(test_engine, "alice")),
            sign_in(TestClient(app.app), test_engine, user_by_name(test_engine, "admin")),
        )


def _add(admin: TestClient, name: str = "Mưa rơi", filename: str = "mua.mp3", data: bytes = MP3):
    return admin.post("/api/admin/ambient", data={"name": name}, files={"file": (filename, io.BytesIO(data))})


def test_only_admins_manage_the_library(people, app: TestClient) -> None:  # noqa: F811
    alice, admin = people
    for call in (lambda c: _add(c), lambda c: c.patch("/api/admin/ambient/1", json={"name": "x"}), lambda c: c.delete("/api/admin/ambient/1")):
        assert call(app).status_code == 401
        assert call(alice).status_code == 403
    assert _add(admin).status_code == 201


def test_library_add_list_play_rename_delete(people, app: TestClient) -> None:  # noqa: F811
    alice, admin = people
    created = _add(admin, "  Tiếng   mưa ").json()
    assert created["name"] == "Tiếng mưa" and created["url"] == f"/api/ambient/{created['id']}/audio"
    assert [t["id"] for t in alice.get("/api/ambient").json()] == [created["id"]]  # any signed-in user lists it
    assert app.get("/api/ambient").status_code == 401  # but not an anonymous visitor
    audio = app.get(created["url"])  # while the file itself needs no token: an <audio> element cannot send one
    assert audio.status_code == 200 and audio.headers["content-type"] == "audio/mpeg" and audio.content == MP3

    assert admin.patch(f"/api/admin/ambient/{created['id']}", json={"name": "Mưa nhẹ"}).json()["name"] == "Mưa nhẹ"
    assert admin.patch(f"/api/admin/ambient/{created['id']}", json={"name": " "}).status_code == 400
    assert admin.patch("/api/admin/ambient/999", json={"name": "x"}).status_code == 404

    assert len(list(ambient_dir().iterdir())) == 1
    assert admin.delete(f"/api/admin/ambient/{created['id']}").status_code == 204
    assert list(ambient_dir().iterdir()) == [] and app.get(created["url"]).status_code == 404
    assert admin.delete(f"/api/admin/ambient/{created['id']}").status_code == 404


def test_only_real_audio_is_accepted(people) -> None:
    _, admin = people
    assert _add(admin, filename="x.exe").status_code == 400  # wrong extension
    assert _add(admin, filename="x.mp3", data=b"not audio at all").status_code == 400  # renamed document
    assert _add(admin, filename="x.mp3", data=b"").status_code == 400
    assert _add(admin, filename="x.mp3", data=b"ID3" + b"\x00" * (16 * 1024 * 1024)).status_code == 400  # over 15 MB
    assert _add(admin, name="Sóng", filename="song.wav", data=_wav()).status_code == 201
    assert list(ambient_dir().iterdir())[0].suffix == ".wav"  # stored under a random name, never the uploaded one


def test_path_traversal_is_impossible(app: TestClient) -> None:  # noqa: F811
    from src.core.audio.ambient import ambient_path

    assert ambient_path("../../etc/passwd") is None and ambient_path("a" * 32 + ".mp3") is None


def test_each_person_chooses_their_own_sound(people) -> None:
    alice, admin = people
    track = _add(admin).json()["id"]
    assert alice.get("/api/settings").json()["ambient_track"] == 0  # off until chosen
    base = {k: alice.get("/api/settings").json()[k] for k in ("prefetch_count", "default_speed", "default_voice", "daily_char_limit")}

    saved = alice.put("/api/settings", json={**base, "ambient_track": track, "ambient_volume": 0.25, "chapter_chime": False}).json()
    assert (saved["ambient_track"], saved["ambient_volume"], saved["chapter_chime"]) == (track, 0.25, False)
    assert admin.get("/api/settings").json()["ambient_track"] == 0  # the admin's own choice is untouched

    # An older client that sends only the old fields must not wipe the choice.
    assert alice.put("/api/settings", json={**base, "default_speed": 1.25}).json()["ambient_track"] == track
    assert alice.put("/api/settings", json={**base, "ambient_track": 999}).status_code == 400
    assert alice.put("/api/settings", json={**base, "ambient_volume": 1.5}).status_code == 400

    admin.delete(f"/api/admin/ambient/{track}")  # the sound is removed: it reads as "none"
    assert alice.get("/api/settings").json()["ambient_track"] == 0
