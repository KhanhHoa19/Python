"""Accounts: registration, login, tokens, throttling, and that one user never reaches another's data."""

from __future__ import annotations

import io
import time
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from src.api.app import create_app
from src.api.routes import auth as auth_routes
from src.core.auth.security import (
    LoginThrottle,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from src.core.auth.users import SqlUserRepository, jwt_secret
from src.core.models.book import Book, BookSentence
from src.core.storage.repositories import SqlBookRepository
from tests.auth_helpers import make_user, sign_in, use_engine, user_by_name
from tests.integration.test_api_extended import provider  # noqa: F401  (fixture used by `app` below)


@pytest.fixture
def app(test_engine: Engine, provider, tmp_path, monkeypatch) -> Generator[TestClient, None, None]:  # noqa: F811
    """An app with NO signed-in client: every test chooses who is calling."""
    from contextlib import ExitStack
    from unittest.mock import patch

    from src.core.config import get_settings

    for var, name in (("AUDIO_CACHE_DIR", "cache"), ("EXPORT_DIR", "exports"), ("VOICE_SAMPLES_DIR", "samples")):
        monkeypatch.setenv(var, str(tmp_path / name))
    get_settings.cache_clear()
    auth_routes._throttle.__init__()  # type: ignore[misc]  # a fresh failure count for every test
    with ExitStack() as stack:
        stack.enter_context(use_engine(test_engine))
        for target in (
            "src.core.player.audio_service.TTSFactory", "src.api.routes.voices.TTSFactory",
            "src.api.routes.settings.TTSFactory", "src.api.routes.health.TTSFactory",
        ):
            stack.enter_context(patch(target)).create_provider.return_value = provider
        with TestClient(create_app()) as client:
            yield client
    get_settings.cache_clear()


def _register(app: TestClient, username: str, password: str = "correct horse") -> dict:
    resp = app.post("/api/auth/register", json={"username": username, "password": password, "full_name": username})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _as(app: TestClient, token: str) -> TestClient:
    other = TestClient(app.app)
    other.headers["Authorization"] = f"Bearer {token}"
    return other


SECRET = "unit-test-secret-" * 3  # 48 bytes: long enough for HS256

# ---------------------------------------------------------------- passwords and tokens

def test_password_hash_is_salted_and_verifies() -> None:
    first, second = hash_password("secret-pass"), hash_password("secret-pass")
    assert first != second and first.startswith("scrypt$")
    assert verify_password("secret-pass", first) and not verify_password("Secret-pass", first)


def test_malformed_hashes_never_verify() -> None:
    for stored in ("", "x", "scrypt$1$2", "md5$a$b$c$d$e", "scrypt$16384$8$1$zz$zz"):
        assert verify_password("anything", stored) is False


def test_token_roundtrip_expiry_and_wrong_secret() -> None:
    token, lifetime = create_access_token(7, "user", SECRET, 2)
    assert lifetime == 7200
    claims = decode_access_token(token, SECRET)
    assert claims is not None and claims["sub"] == "7" and claims["role"] == "user"
    assert decode_access_token(token, SECRET + "x") is None
    expired = jwt.encode({"sub": "7", "exp": int(time.time()) - 5}, SECRET, algorithm="HS256")
    assert decode_access_token(expired, SECRET) is None
    assert decode_access_token("not.a.token", SECRET) is None
    unsigned = jwt.encode({"sub": "7", "exp": int(time.time()) + 60}, None, algorithm="none")
    assert decode_access_token(unsigned, SECRET) is None  # "alg: none" is refused


def test_throttle_blocks_then_forgets() -> None:
    now = [0.0]
    throttle = LoginThrottle(max_failures=3, window_seconds=60, clock=lambda: now[0])
    for _ in range(3):
        assert not throttle.is_blocked("a")
        throttle.record_failure("a")
    assert throttle.is_blocked("a") and 0 < throttle.retry_after("a") <= 60
    assert not throttle.is_blocked("b")
    now[0] = 61
    assert not throttle.is_blocked("a")
    throttle.record_failure("a")
    throttle.reset("a")
    assert not throttle.is_blocked("a")


# ---------------------------------------------------------------- register / login / me

def test_register_login_and_me(app: TestClient) -> None:
    body = _register(app, "Lan.Nguyen")
    assert body["user"]["username"] == "lan.nguyen" and body["user"]["role"] == "user" and body["expires_in"] > 0
    me = _as(app, body["access_token"]).get("/api/auth/me")
    assert me.status_code == 200 and me.json()["username"] == "lan.nguyen"

    login = app.post("/api/auth/login", json={"username": "LAN.NGUYEN", "password": "correct horse"})
    assert login.status_code == 200 and login.json()["user"]["id"] == body["user"]["id"]


def test_registration_rules(app: TestClient) -> None:
    _register(app, "minh")
    assert app.post("/api/auth/register", json={"username": "MINH", "password": "another pass"}).status_code == 409
    for bad in ({"username": "ab", "password": "long enough"}, {"username": "has space", "password": "long enough"},
                {"username": "valid_name", "password": "short"}, {"username": "x" * 40, "password": "long enough"}):
        assert app.post("/api/auth/register", json=bad).status_code == 400, bad
    assert app.post("/api/auth/register", json={"username": "boss", "password": "long enough", "role": "admin"}).json()["user"]["role"] == "user"


def test_wrong_password_and_unknown_user_look_the_same(app: TestClient) -> None:
    _register(app, "annie")
    wrong = app.post("/api/auth/login", json={"username": "annie", "password": "nope nope"})
    unknown = app.post("/api/auth/login", json={"username": "nobody", "password": "nope nope"})
    assert wrong.status_code == unknown.status_code == 401 and wrong.json() == unknown.json()


def test_login_is_throttled_after_repeated_failures(app: TestClient) -> None:
    _register(app, "binh")
    for _ in range(5):
        assert app.post("/api/auth/login", json={"username": "binh", "password": "wrong pass"}).status_code == 401
    blocked = app.post("/api/auth/login", json={"username": "binh", "password": "correct horse"})
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) > 0


def test_every_data_endpoint_needs_a_token(app: TestClient) -> None:
    assert app.get("/api/health").status_code == 200
    for method, url in (
        ("get", "/api/books"), ("get", "/api/books/1/sentences"), ("get", "/api/books/1/chapters"),
        ("get", "/api/audio/1/0"), ("get", "/api/bookmarks/1"), ("post", "/api/bookmarks"), ("post", "/api/sessions"),
        ("get", "/api/voices"), ("post", "/api/voices/clone"), ("get", "/api/notes"), ("get", "/api/settings"),
        ("put", "/api/settings"), ("get", "/api/analytics/daily"), ("get", "/api/analytics/voices"),
        ("get", "/api/books/1/export/estimate"), ("post", "/api/books/1/export"), ("get", "/api/exports/x"),
        ("get", "/api/health/network"), ("post", "/api/tts/verify"), ("get", "/api/auth/me"),
    ):
        assert getattr(app, method)(url).status_code == 401, f"{method.upper()} {url} is open"


def test_bad_tokens_are_rejected(app: TestClient, test_engine: Engine) -> None:
    secret = jwt_secret(test_engine)
    expired = jwt.encode({"sub": "2", "exp": int(time.time()) - 10}, secret, algorithm="HS256")
    forged = jwt.encode({"sub": "1", "role": "admin", "exp": int(time.time()) + 600}, "guess-" * 8, algorithm="HS256")
    gone = jwt.encode({"sub": "9999", "exp": int(time.time()) + 600}, secret, algorithm="HS256")
    for token in (expired, forged, gone, "garbage"):
        assert _as(app, token).get("/api/books").status_code == 401


def test_a_deleted_account_loses_access_at_once(app: TestClient, test_engine: Engine) -> None:
    body = _register(app, "temp")
    with test_engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": body["user"]["id"]})
    assert _as(app, body["access_token"]).get("/api/books").status_code == 401


# ---------------------------------------------------------------- isolation between users

def _book(engine: Engine, owner: int | None, title: str = "Sách", public: bool = False, hash_char: str = "a") -> int:
    sentences = [
        BookSentence(id=None, book_id=0, chapter_index=1, sentence_index=i, text_content=f"Câu {i}.",
                     word_count=2, content_hash=f"{i:064d}") for i in range(2)
    ]
    book = Book(id=None, title=title, author="A", source_path="/srv/secret/path.txt", content_hash=hash_char * 64,
                total_chapters=1, total_sentences=2, total_words=4, owner_id=owner, is_public=public)
    return SqlBookRepository(engine).save_book(book, sentences)


@pytest.fixture
def two_users(app: TestClient, test_engine: Engine):
    alice = make_user(test_engine, "alice")
    bob = make_user(test_engine, "bob")
    return app, sign_in(TestClient(app.app), test_engine, alice), sign_in(TestClient(app.app), test_engine, bob), alice, bob


def test_a_private_book_is_invisible_to_everyone_else(two_users, test_engine: Engine) -> None:
    _, alice_c, bob_c, alice, _ = two_users
    book_id = _book(test_engine, alice.id, "Của Alice")
    assert [b["title"] for b in alice_c.get("/api/books").json()] == ["Của Alice"]
    assert bob_c.get("/api/books").json() == []
    admin_c = sign_in(TestClient(alice_c.app), test_engine, user_by_name(test_engine, "admin"))
    assert admin_c.get("/api/books").json() == []  # not even the administrator
    for client in (bob_c, admin_c):
        assert client.get(f"/api/books/{book_id}").status_code == 404
        assert client.get(f"/api/books/{book_id}/sentences").status_code == 404
        assert client.get(f"/api/books/{book_id}/chapters").status_code == 404
        assert client.get(f"/api/audio/{book_id}/0").status_code == 404
        assert client.get(f"/api/bookmarks/{book_id}").status_code == 404
        assert client.get(f"/api/books/{book_id}/export/estimate").status_code == 404
        assert client.patch(f"/api/books/{book_id}", json={"title": "Hack"}).status_code == 404
        assert client.delete(f"/api/books/{book_id}").status_code == 404
        assert client.post("/api/bookmarks", json={"book_id": book_id, "current_sentence_index": 1}).status_code == 404
        assert client.post("/api/notes", json={"book_id": book_id, "sentence_index": 0, "start_offset": 0, "end_offset": 3}).status_code == 404
    assert alice_c.get(f"/api/books/{book_id}").json()["title"] == "Của Alice"


def test_server_paths_are_only_shown_to_the_owner(two_users, test_engine: Engine) -> None:
    _, alice_c, bob_c, alice, _ = two_users
    book_id = _book(test_engine, alice.id, public=True)
    assert alice_c.get(f"/api/books/{book_id}").json()["source_path"] == "/srv/secret/path.txt"
    assert bob_c.get(f"/api/books/{book_id}").json()["source_path"] == ""


def test_public_books_are_shared_but_progress_is_personal(two_users, test_engine: Engine) -> None:
    _, alice_c, bob_c, _, _ = two_users
    book_id = _book(test_engine, owner=user_by_name(test_engine, "admin").id, title="Sách chung", public=True)
    assert bob_c.get("/api/books").json() == []  # public books are in the catalogue, not on the shelf, until added
    listed = bob_c.get("/api/books/explore").json()
    assert listed[0]["title"] == "Sách chung" and listed[0]["is_mine"] is False and listed[0]["on_shelf"] is False
    assert bob_c.post(f"/api/books/{book_id}/shelf").status_code == 204
    assert bob_c.get("/api/books").json()[0]["title"] == "Sách chung"
    assert alice_c.post("/api/bookmarks", json={"book_id": book_id, "current_sentence_index": 1, "voice": "mock-vi-male"}).status_code == 200
    assert alice_c.get(f"/api/bookmarks/{book_id}").json()["current_sentence_index"] == 1
    fresh = bob_c.get(f"/api/bookmarks/{book_id}").json()
    assert fresh["current_sentence_index"] == 0 and fresh["voice"] is None  # Alice's place is not Bob's
    assert bob_c.get(f"/api/audio/{book_id}/0").status_code == 200  # but he can listen


def test_nobody_edits_a_public_book_except_an_admin(two_users, test_engine: Engine) -> None:
    _, alice_c, bob_c, _, _ = two_users
    admin = user_by_name(test_engine, "admin")
    book_id = _book(test_engine, admin.id, public=True)
    assert alice_c.patch(f"/api/books/{book_id}", json={"title": "Mine now"}).status_code == 403
    assert bob_c.delete(f"/api/books/{book_id}").status_code == 403
    admin_c = sign_in(TestClient(alice_c.app), test_engine, admin)
    assert admin_c.patch(f"/api/books/{book_id}", json={"title": "Renamed"}).json()["title"] == "Renamed"


def test_only_an_admin_can_upload_a_public_book(two_users, test_engine: Engine) -> None:
    _, alice_c, _, _, _ = two_users
    files = {"file": ("a.txt", io.BytesIO("Một câu. Hai câu.".encode()))}
    assert alice_c.post("/api/books/ingest", files=files, data={"is_public": "true"}).status_code == 403
    admin_c = sign_in(TestClient(alice_c.app), test_engine, user_by_name(test_engine, "admin"))
    ok = admin_c.post("/api/books/ingest", files={"file": ("b.txt", io.BytesIO("Ba câu. Bốn câu.".encode()))}, data={"is_public": "true"})
    assert ok.status_code == 201
    assert any(b["title"] == "B" and b["is_public"] for b in alice_c.get("/api/books/explore").json())


def test_two_people_can_each_upload_the_same_file(two_users) -> None:
    _, alice_c, bob_c, _, _ = two_users
    data = "Một câu. Hai câu. Ba câu.".encode()
    first = alice_c.post("/api/books/ingest", files={"file": ("x.txt", io.BytesIO(data))})
    second = bob_c.post("/api/books/ingest", files={"file": ("x.txt", io.BytesIO(data))})
    again = alice_c.post("/api/books/ingest", files={"file": ("x.txt", io.BytesIO(data))})
    assert first.status_code == second.status_code == 201
    assert first.json()["book_id"] != second.json()["book_id"]  # no "already exists" leak between people
    assert again.json()["book_id"] == first.json()["book_id"]  # the same person still gets de-duplication


def test_sessions_notes_and_stats_are_personal(two_users, test_engine: Engine) -> None:
    _, alice_c, bob_c, _, _ = two_users
    admin = user_by_name(test_engine, "admin")
    book_id = _book(test_engine, admin.id, public=True)
    now = datetime.now(UTC)
    session = {"book_id": book_id, "duration_seconds": 600, "sentences_read": 2, "words_read": 20,
               "start_time": (now - timedelta(minutes=10)).isoformat(), "end_time": now.isoformat(), "voice": "mock-vi-male"}
    assert alice_c.post("/api/sessions", json=session).status_code == 201
    assert alice_c.get("/api/analytics/daily?days=1").json()[-1]["minutes"] == 10.0
    assert bob_c.get("/api/analytics/daily?days=1").json()[-1]["minutes"] == 0.0
    assert [v["voice"] for v in alice_c.get("/api/analytics/voices").json()] == ["mock-vi-male"]
    assert bob_c.get("/api/analytics/voices").json() == []
    assert bob_c.get("/api/analytics/summary").json()["total_sessions"] == 0

    note = alice_c.post("/api/notes", json={"book_id": book_id, "sentence_index": 0, "start_offset": 0, "end_offset": 3, "note_text": "riêng"})
    assert note.status_code == 201
    note_id = note.json()["id"]
    assert bob_c.get("/api/notes").json() == []
    assert bob_c.get(f"/api/notes/{note_id}/audio").status_code == 404
    assert bob_c.patch(f"/api/notes/{note_id}", json={"note_text": "hack"}).status_code == 404
    assert bob_c.delete(f"/api/notes/{note_id}").status_code == 404
    assert [n["note_text"] for n in alice_c.get("/api/notes").json()] == ["riêng"]


def test_a_cloned_voice_belongs_to_its_owner(two_users, test_engine: Engine) -> None:
    from src.core.storage.repositories import SqlVoiceRepository

    _, alice_c, bob_c, alice, _ = two_users
    SqlVoiceRepository(test_engine).add_voice(
        "private-clone-1", "mock", "Giọng của Alice", "vi", None, None, datetime.now(UTC), owner_id=alice.id)
    book_id = _book(test_engine, alice.id)
    assert "private-clone-1" in [v["voice_id"] for v in alice_c.get("/api/voices").json()["voices"]]
    assert "private-clone-1" not in [v["voice_id"] for v in bob_c.get("/api/voices").json()["voices"]]
    assert bob_c.get("/api/voices/private-clone-1/preview").status_code == 404
    assert bob_c.delete("/api/voices/private-clone-1").status_code == 404
    admin_c = sign_in(TestClient(alice_c.app), test_engine, user_by_name(test_engine, "admin"))
    assert admin_c.delete("/api/voices/private-clone-1").status_code == 404  # not even the administrator
    assert alice_c.get(f"/api/audio/{book_id}/0?voice=private-clone-1").status_code == 200
    # Bob cannot borrow it for a public book either
    public_id = _book(test_engine, user_by_name(test_engine, "admin").id, public=True, hash_char="b")
    assert bob_c.get(f"/api/audio/{public_id}/0?voice=private-clone-1").status_code == 404
    assert bob_c.post("/api/bookmarks", json={"book_id": public_id, "current_sentence_index": 0, "voice": "private-clone-1"}).status_code == 404


def test_export_jobs_belong_to_whoever_started_them(two_users, test_engine: Engine) -> None:
    _, alice_c, bob_c, alice, _ = two_users
    book_id = _book(test_engine, alice.id)
    job = alice_c.post(f"/api/books/{book_id}/export", json={}).json()["job_id"]
    assert alice_c.get(f"/api/exports/{job}").status_code == 200
    for client in (bob_c, sign_in(TestClient(alice_c.app), test_engine, user_by_name(test_engine, "admin"))):
        assert client.get(f"/api/exports/{job}").status_code == 404
        assert client.get(f"/api/exports/{job}/file").status_code == 404
        assert client.delete(f"/api/exports/{job}").status_code == 404


def test_voice_limit_per_user_but_not_for_admin(two_users, test_engine: Engine, monkeypatch) -> None:
    import wave

    from src.core.config import get_settings

    monkeypatch.setenv("MAX_VOICES_PER_USER", "1")
    get_settings.cache_clear()
    _, alice_c, _, _, _ = two_users

    def clone(client: TestClient, name: str):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(8000)
            w.writeframes(b"\x00\x00" * 8000 * 6)
        return client.post("/api/voices/clone", files={"sample": ("s.wav", buf.getvalue())},
                           data={"name": name, "language": "vi", "consent": "true"})

    assert clone(alice_c, "Một").status_code == 201
    over = clone(alice_c, "Hai")
    assert over.status_code == 403 and "at most 1" in over.json()["error"]
    admin_c = sign_in(TestClient(alice_c.app), test_engine, user_by_name(test_engine, "admin"))
    assert clone(admin_c, "A1").status_code == 201 and clone(admin_c, "A2").status_code == 201
    assert SqlUserRepository(test_engine).count() >= 3


# ---------------------------------------------------------------- maintenance tool

def test_reset_password_changes_the_login(app: TestClient, test_engine: Engine, capsys) -> None:
    from unittest.mock import patch

    from src.core.auth import admin_cli

    _register(app, "forgetful")
    with patch("src.core.auth.admin_cli.get_db_engine", return_value=test_engine):
        assert admin_cli.reset_password("FORGETFUL", "brand new pass") == 0
        assert admin_cli.reset_password("forgetful", "short") == 1  # too short: nothing changes
        assert admin_cli.reset_password("nobody", "long enough pass") == 1
        assert admin_cli.list_users() == 0
    assert "forgetful" in capsys.readouterr().out
    assert app.post("/api/auth/login", json={"username": "forgetful", "password": "correct horse"}).status_code == 401
    assert app.post("/api/auth/login", json={"username": "forgetful", "password": "brand new pass"}).status_code == 200
