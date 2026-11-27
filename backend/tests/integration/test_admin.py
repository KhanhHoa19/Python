"""Administrator panel and the voice studio: only admins get in, and an admin still cannot read private data."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from src.core.storage.repositories import SqlBookRepository, SqlVoiceRepository
from tests.auth_helpers import make_user, sign_in, user_by_name
from tests.integration.test_accounts import _book, app  # noqa: F401  (fixture and helper)
from tests.integration.test_api_extended import provider  # noqa: F401


@pytest.fixture
def people(app: TestClient, test_engine: Engine, provider):  # noqa: F811
    alice = make_user(test_engine, "alice")
    with patch("src.api.routes.admin.TTSFactory") as factory:
        factory.create_provider.return_value = provider
        yield (
            sign_in(TestClient(app.app), test_engine, alice),
            sign_in(TestClient(app.app), test_engine, user_by_name(test_engine, "admin")),
            alice, user_by_name(test_engine, "admin"),
        )


def _clone(engine: Engine, voice_id: str, owner: int, public: bool = False) -> None:
    SqlVoiceRepository(engine).add_voice(
        voice_id, "mock", f"Giọng {voice_id}", "vi", None, None, datetime.now(UTC), owner_id=owner, is_public=public)


ADMIN_ROUTES = [
    ("get", "/api/admin/books"), ("put", "/api/admin/books/1/public"), ("get", "/api/admin/categories"),
    ("post", "/api/admin/categories"), ("put", "/api/admin/categories/1"), ("delete", "/api/admin/categories/1"),
    ("get", "/api/admin/voices"), ("put", "/api/admin/voices/x/public"), ("put", "/api/admin/default-voice"),
    ("get", "/api/admin/users"),
]


def test_only_admins_reach_the_panel(people, app: TestClient) -> None:  # noqa: F811
    alice_c, admin_c, *_ = people
    for method, url in ADMIN_ROUTES:
        assert getattr(app, method)(url).status_code == 401, url  # not signed in
        assert alice_c.request(method.upper(), url, json={} if method != "get" else None).status_code == 403, url
    assert admin_c.get("/api/admin/users").status_code == 200


def test_admin_publishes_only_own_books_and_never_sees_private_ones(people, test_engine: Engine) -> None:
    alice_c, admin_c, alice, admin = people
    secret = _book(test_engine, alice.id, "Bí mật của Alice", hash_char="b")
    mine = _book(test_engine, admin.id, "Sách của admin", hash_char="c")
    listed = {b["id"] for b in admin_c.get("/api/admin/books").json()}
    assert mine in listed and secret not in listed
    assert admin_c.put(f"/api/admin/books/{secret}/public", json={"is_public": True}).status_code == 404
    assert not SqlBookRepository(test_engine).get_by_id(secret).is_public

    done = admin_c.put(f"/api/admin/books/{mine}/public", json={"is_public": True})
    assert done.status_code == 200 and done.json()["is_public"] is True
    # Alice adds it to her shelf: the admin catalogue counts that shelf.
    assert alice_c.post(f"/api/books/{mine}/shelf").status_code in (200, 201, 204)
    assert next(b for b in admin_c.get("/api/admin/books").json() if b["id"] == mine)["shelf_count"] == 1
    assert admin_c.put(f"/api/admin/books/{mine}/public", json={"is_public": False}).json()["is_public"] is False


def test_category_management(people, test_engine: Engine) -> None:
    alice_c, admin_c, alice, admin = people
    created = admin_c.post("/api/admin/categories", json={"name": "Văn Hóa Việt", "color": "#336699"})
    assert created.status_code == 201
    cat = created.json()
    assert cat["slug"] == "van-hoa-viet" and cat["book_count"] == 0
    assert admin_c.post("/api/admin/categories", json={"name": "van hoa viet"}).status_code == 409  # same tag, no accents
    assert admin_c.post("/api/admin/categories", json={"name": "Lịch sử"}).status_code == 409  # a default tag
    assert admin_c.post("/api/admin/categories", json={"name": "  "}).status_code == 400
    assert admin_c.post("/api/admin/categories", json={"name": "X", "color": "red"}).status_code == 400
    assert cat["id"] in {c["id"] for c in alice_c.get("/api/categories").json()}  # visible to everyone

    renamed = admin_c.put(f"/api/admin/categories/{cat['id']}", json={"name": "Văn hóa", "color": "#112233"}).json()
    assert renamed["name"] == "Văn hóa" and renamed["slug"] == "van-hoa-viet"  # slug is stable

    book = _book(test_engine, alice.id)
    SqlBookRepository(test_engine).set_category(book, cat["id"])
    assert next(c for c in admin_c.get("/api/admin/categories").json() if c["id"] == cat["id"])["book_count"] == 1
    assert admin_c.delete(f"/api/admin/categories/{cat['id']}").status_code == 204
    assert SqlBookRepository(test_engine).get_by_id(book).category_id is None  # the book survives, uncategorised
    assert admin_c.delete(f"/api/admin/categories/{cat['id']}").status_code == 404

    khac = next(c for c in admin_c.get("/api/admin/categories").json() if c["slug"] == "khac")
    assert admin_c.delete(f"/api/admin/categories/{khac['id']}").status_code == 400


def test_system_voices_and_default_voice(people, test_engine: Engine) -> None:
    alice_c, admin_c, alice, admin = people
    _clone(test_engine, "alice-private", alice.id)
    _clone(test_engine, "admin-own", admin.id)
    ids = {v["voice_id"] for v in admin_c.get("/api/admin/voices").json()["voices"]}
    assert "admin-own" in ids and "alice-private" not in ids
    assert admin_c.put("/api/admin/voices/alice-private/public", json={"is_public": True}).status_code == 404
    assert admin_c.put("/api/admin/default-voice", json={"voice_id": "alice-private"}).status_code == 404
    assert admin_c.put("/api/admin/default-voice", json={"voice_id": "admin-own"}).status_code == 400  # not public yet
    assert admin_c.put("/api/admin/default-voice", json={"voice_id": "nope"}).status_code == 404

    assert admin_c.put("/api/admin/voices/admin-own/public", json={"is_public": True}).json()["is_public"] is True
    shared = next(v for v in alice_c.get("/api/voices").json()["voices"] if v["voice_id"] == "admin-own")
    assert shared["is_public"] and not shared["is_mine"]
    result = admin_c.put("/api/admin/default-voice", json={"voice_id": "admin-own"}).json()
    assert result["default_voice"] == "admin-own"
    # Alice never chose a voice, so she starts with the system default; her own choice still wins.
    assert alice_c.get("/api/settings").json()["default_voice"] == "admin-own"
    assert alice_c.get("/api/voices").json()["system_default_voice"] == "admin-own"


def test_voice_rename_and_limits(people, test_engine: Engine) -> None:
    alice_c, admin_c, alice, admin = people
    _clone(test_engine, "alice-v", alice.id)
    _clone(test_engine, "pub", admin.id, public=True)
    listing = alice_c.get("/api/voices").json()
    assert listing["my_voice_count"] == 1 and listing["max_voices"] == 3
    assert admin_c.get("/api/voices").json()["max_voices"] is None

    assert alice_c.patch("/api/voices/alice-v", json={"display_name": "  Giọng   mới "}).json()["display_name"] == "Giọng mới"
    assert alice_c.patch("/api/voices/alice-v", json={"display_name": " "}).status_code == 400
    assert alice_c.patch("/api/voices/pub", json={"display_name": "hack"}).status_code == 403  # public but not hers
    assert admin_c.patch("/api/voices/alice-v", json={"display_name": "hack"}).status_code == 404  # private to Alice
    assert admin_c.patch("/api/voices/pub", json={"display_name": "Công khai"}).status_code == 200


def test_user_list_shows_accounts_only(people, test_engine: Engine) -> None:
    alice_c, admin_c, alice, _ = people
    _book(test_engine, alice.id, "Sách riêng")
    users = {u["username"]: u for u in admin_c.get("/api/admin/users").json()}
    assert users["alice"]["book_count"] == 1 and users["alice"]["role"] == "user"
    assert "password_hash" not in users["alice"] and set(users["alice"]) == {
        "id", "username", "full_name", "role", "created_at", "book_count", "voice_count"}


def test_admin_manages_system_books_but_not_other_peoples_books(people, test_engine: Engine) -> None:
    alice_c, admin_c, alice, admin = people
    system = _book(test_engine, admin.id, "Sách hệ thống", public=True, hash_char="d")
    secret = _book(test_engine, alice.id, "Của Alice", hash_char="e")

    edited = admin_c.patch(f"/api/books/{system}", json={"title": "Tên mới", "author": "  Tác   giả  mới "})
    assert edited.status_code == 200 and edited.json()["author"] == "Tác giả mới"
    assert SqlBookRepository(test_engine).get_by_id(system).search_text == "ten moi tac gia moi"  # search follows the edit
    assert admin_c.patch(f"/api/books/{system}", json={"author": ""}).json()["author"] == ""
    assert admin_c.patch(f"/api/books/{system}", json={}).status_code == 400

    assert alice_c.patch(f"/api/books/{system}", json={"title": "hack"}).status_code == 403  # a member may not
    assert alice_c.delete(f"/api/books/{system}").status_code == 403
    assert admin_c.patch(f"/api/books/{secret}", json={"title": "hack"}).status_code == 404  # nor may the admin, on private ones
    assert admin_c.delete(f"/api/books/{secret}").status_code == 404

    assert alice_c.post(f"/api/books/{system}/shelf").status_code in (200, 201, 204)
    assert admin_c.delete(f"/api/books/{system}").status_code == 204
    assert SqlBookRepository(test_engine).get_by_id(system) is None
    assert system not in {b["id"] for b in alice_c.get("/api/books").json()}  # gone from her shelf too
    assert SqlBookRepository(test_engine).get_by_id(secret) is not None
