"""The recommendation endpoint: personal, public-only, and it never leaks anyone else's data."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from src.core.storage.repositories import SqlBookRepository, SqlShelfRepository
from tests.auth_helpers import make_user, sign_in, user_by_name
from tests.integration.test_accounts import _book, app  # noqa: F401  (fixture and helper)
from tests.integration.test_api_extended import provider  # noqa: F401


def _category(engine: Engine, slug: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text("SELECT id FROM categories WHERE slug = :s"), {"s": slug}).scalar())


def _public(engine: Engine, owner: int, title: str, slug: str, hash_char: str) -> int:
    book_id = _book(engine, owner, title, public=True, hash_char=hash_char)
    SqlBookRepository(engine).set_category(book_id, _category(engine, slug))
    return book_id


def _session(engine: Engine, user_id: int, book_id: int, minutes: int) -> None:
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO reading_sessions (book_id, user_id, start_time, end_time, duration_seconds, sentences_read, words_read) "
            "VALUES (:b, :u, :t, :t, :d, 50, :w)"),
            {"b": book_id, "u": user_id, "t": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"), "d": minutes * 60, "w": minutes * 150})


@pytest.fixture
def world(app: TestClient, test_engine: Engine, provider):  # noqa: F811
    admin = user_by_name(test_engine, "admin")
    alice, bob = make_user(test_engine, "alice"), make_user(test_engine, "bob")
    books = {
        "crime": _public(test_engine, admin.id, "Vụ án", "trinh-tham", "a"),
        "ghost": _public(test_engine, admin.id, "Căn phòng", "kinh-di", "b"),
        "science": _public(test_engine, admin.id, "Bầu trời", "khoa-hoc", "c"),
        "kids": _public(test_engine, admin.id, "Chú thỏ", "thieu-nhi", "d"),
    }
    clients = {n: sign_in(TestClient(app.app), test_engine, u) for n, u in (("alice", alice), ("bob", bob))}
    return clients["alice"], clients["bob"], alice, bob, books, test_engine


def _titles(response) -> list[str]:
    assert response.status_code == 200, response.text
    return [b["title"] for b in response.json()["items"]]


def test_a_new_reader_is_asked_first_and_sees_every_public_book(world) -> None:
    alice, _, _, _, _, _ = world
    body = alice.get("/api/recommendations").json()
    assert body["onboarded"] is False and body["has_history"] is False and body["favorite_categories"] == []
    assert len(body["items"]) == 4 and len(body["moods"]) == 6
    assert all(i["is_public"] and not i["on_shelf"] and i["estimated_minutes"] >= 1 for i in body["items"])


def test_chosen_categories_lead_and_can_be_changed_later(world) -> None:
    alice, *_ = world
    saved = alice.put("/api/recommendations/preferences", json={"favorite_categories": ["khoa-hoc", "khoa-hoc"]}).json()
    assert saved["favorite_categories"] == ["khoa-hoc"] and saved["onboarded"] is True  # no duplicates
    assert saved["items"][0]["title"] == "Bầu trời" and "Bạn đã chọn thích Khoa học" in saved["items"][0]["reasons"]
    changed = alice.put("/api/recommendations/preferences", json={"favorite_categories": ["thieu-nhi"]}).json()
    assert changed["items"][0]["title"] == "Chú thỏ"
    skipped = alice.put("/api/recommendations/preferences", json={"favorite_categories": [], "onboarded": True}).json()
    assert skipped["favorite_categories"] == [] and skipped["onboarded"] is True  # "skip" is remembered too
    assert alice.put("/api/recommendations/preferences", json={"favorite_categories": ["khong-co"]}).status_code == 400


def test_history_shapes_the_ranking_and_shelved_books_disappear(world) -> None:
    alice, _, alice_user, _, books, engine = world
    SqlShelfRepository(engine, alice_user.id).add(books["crime"])
    _session(engine, alice_user.id, books["crime"], 90)
    body = alice.get("/api/recommendations").json()
    assert body["has_history"] is True and "Vụ án" not in [i["title"] for i in body["items"]]  # already on her shelf
    assert body["top_categories"][0]["slug"] == "trinh-tham"
    assert body["items"][0]["title"] in ("Căn phòng", "Bầu trời", "Chú thỏ")


def test_mood_and_duration_filters(world) -> None:
    alice, _, _, _, books, engine = world
    thrill = _titles(alice.get("/api/recommendations?mood=hoi-hop"))
    assert sorted(thrill) == ["Căn phòng", "Vụ án"]
    assert _titles(alice.get("/api/recommendations?mood=lang-man")) == []  # no romance among them: empty, not an error
    assert alice.get("/api/recommendations?mood=buon").status_code == 400
    with engine.begin() as conn:
        conn.execute(text("UPDATE books SET total_words = 150 * 120 WHERE id = :id"), {"id": books["science"]})  # a 2-hour book
    assert "Bầu trời" not in _titles(alice.get("/api/recommendations?max_minutes=60"))
    assert "Bầu trời" in _titles(alice.get("/api/recommendations?max_minutes=180"))
    assert alice.get("/api/recommendations?max_minutes=0").status_code == 400


def test_only_public_books_and_nothing_of_other_readers_leaks(world) -> None:
    alice, bob, alice_user, bob_user, books, engine = world
    secret = _book(engine, alice_user.id, "Bí mật của Alice", hash_char="e")  # private
    SqlBookRepository(engine).set_category(secret, _category(engine, "trinh-tham"))
    _session(engine, alice_user.id, secret, 300)
    for client in (alice, bob):
        assert "Bí mật của Alice" not in _titles(client.get("/api/recommendations"))
    # Alice's heavy crime listening must not change what Bob is shown.
    assert _titles(bob.get("/api/recommendations")) == _titles(bob.get("/api/recommendations"))
    assert bob.get("/api/recommendations").json()["top_categories"] == [] and bob.get("/api/recommendations").json()["has_history"] is False
    assert alice.get("/api/recommendations").json()["has_history"] is True
    bob.put("/api/recommendations/preferences", json={"favorite_categories": ["kinh-di"]})
    assert alice.get("/api/recommendations").json()["favorite_categories"] == []  # preferences are personal
    # Popularity is only a number: how many shelves, never whose.
    SqlShelfRepository(engine, bob_user.id).add(books["science"])
    item = next(i for i in alice.get("/api/recommendations").json()["items"] if i["title"] == "Bầu trời")
    assert set(item) >= {"reasons", "estimated_minutes"} and "owner_id" not in item and "source_path" not in item
