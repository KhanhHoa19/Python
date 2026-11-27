"""Smart shelf, public catalogue, categories, accent-free search and covers."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import Engine, text

from src.core.ingestion.covers import (
    COVER_HEIGHT,
    COVER_WIDTH,
    CoverError,
    cover_dir,
    cover_path,
    generate_default_cover,
    normalize_uploaded_cover,
)
from src.core.storage.library import backfill_book_extras
from src.core.storage.migrations import run_migrations
from src.core.text_search import normalize_search, search_tokens
from tests.auth_helpers import make_user, sign_in, user_by_name
from tests.integration.test_accounts import _book, app  # noqa: F401  (fixture and helper)
from tests.integration.test_api_extended import provider  # noqa: F401
from tests.pdf_helpers import build_pdf


def _png(width: int = 800, height: int = 600, color: str = "red") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
def people(app: TestClient, test_engine: Engine):  # noqa: F811
    alice = sign_in(TestClient(app.app), test_engine, make_user(test_engine, "alice"))
    bob = sign_in(TestClient(app.app), test_engine, make_user(test_engine, "bob"))
    admin = sign_in(TestClient(app.app), test_engine, user_by_name(test_engine, "admin"))
    return alice, bob, admin


def _upload(client: TestClient, name: str, data: bytes, **form: str):
    return client.post("/api/books/ingest", files={"file": (name, io.BytesIO(data))}, data=form)


def _titles(response) -> list[str]:
    assert response.status_code == 200, response.text
    return [b["title"] for b in response.json()]


# ---------------------------------------------------------------- search text

def test_search_text_ignores_accents_case_and_spaces() -> None:
    assert normalize_search("  Đắc   Nhân TÂM ") == "dac nhan tam"
    assert normalize_search("Nguyễn Huệ — Tây Sơn") == "nguyen hue — tay son"
    assert search_tokens("dac TAM") == ["dac", "tam"]
    assert search_tokens("   ") == []


def test_search_finds_with_or_without_accents_and_any_word_order(people) -> None:
    alice, _, _ = people
    _upload(alice, "a.txt", "Một câu. Hai câu.".encode(), title="Đắc Nhân Tâm", author="Dale Carnegie")
    _upload(alice, "b.txt", "Ba câu. Bốn câu.".encode(), title="Nhà Giả Kim", author="Paulo Coelho")
    assert _titles(alice.get("/api/books?q=dac nhan tam")) == ["Đắc Nhân Tâm"]
    assert _titles(alice.get("/api/books?q=TÂM đắc")) == ["Đắc Nhân Tâm"]
    assert _titles(alice.get("/api/books?q=carnegie")) == ["Đắc Nhân Tâm"]
    assert _titles(alice.get("/api/books?q=gia kim")) == ["Nhà Giả Kim"]
    assert _titles(alice.get("/api/books?q=khong co")) == []
    assert len(alice.get("/api/books?q=").json()) == 2
    assert _titles(alice.get("/api/books?q=100%25")) == []  # LIKE wildcards in the query are not wildcards


def test_renaming_updates_the_search_text(people) -> None:
    alice, _, _ = people
    book_id = _upload(alice, "a.txt", "Một câu. Hai câu.".encode(), title="Tên cũ").json()["book_id"]
    alice.patch(f"/api/books/{book_id}", json={"title": "Tên Mới Tinh"})
    assert _titles(alice.get("/api/books?q=moi tinh")) == ["Tên Mới Tinh"]
    assert _titles(alice.get("/api/books?q=ten cu")) == []


# ---------------------------------------------------------------- categories

def test_default_categories_and_default_assignment(people) -> None:
    alice, _, _ = people
    categories = alice.get("/api/categories").json()
    assert len(categories) == 15 and categories[-1]["slug"] == "khac"  # "Khác" is always last
    assert {"trinh-tham", "khoa-hoc", "lich-su", "kinh-di", "thieu-nhi"} <= {c["slug"] for c in categories}
    book = _upload(alice, "a.txt", "Một câu. Hai câu.".encode(), title="Chưa chọn").json()
    assert alice.get(f"/api/books/{book['book_id']}").json()["category"]["slug"] == "khac"


def test_filter_by_category_id_or_slug_and_unknown_is_400(people) -> None:
    alice, _, _ = people
    tech = next(c for c in alice.get("/api/categories").json() if c["slug"] == "cong-nghe")
    _upload(alice, "a.txt", "Một câu. Hai câu.".encode(), title="Python", category_id=str(tech["id"]))
    _upload(alice, "b.txt", "Ba câu. Bốn câu.".encode(), title="Tiểu thuyết gì đó")
    assert _titles(alice.get("/api/books?category=cong-nghe")) == ["Python"]
    assert _titles(alice.get(f"/api/books?category={tech['id']}")) == ["Python"]
    assert _titles(alice.get("/api/books?category=khac")) == ["Tiểu thuyết gì đó"]
    assert alice.get("/api/books?category=nope").status_code == 400
    assert _upload(alice, "c.txt", "Năm câu. Sáu câu.".encode(), title="X", category_id="999").json()["book_id"]  # bad id falls back to "Khác"


def test_changing_a_category(people) -> None:
    alice, bob, _ = people
    book_id = _upload(alice, "a.txt", "Một câu. Hai câu.".encode(), title="Sách").json()["book_id"]
    econ = next(c for c in alice.get("/api/categories").json() if c["slug"] == "kinh-te")
    assert alice.patch(f"/api/books/{book_id}", json={"category_id": econ["id"]}).json()["category"]["slug"] == "kinh-te"
    assert alice.patch(f"/api/books/{book_id}", json={"category_id": 999}).status_code == 400
    assert alice.patch(f"/api/books/{book_id}", json={"category_id": None}).json()["category"] is None
    assert alice.patch(f"/api/books/{book_id}", json={}).status_code == 400
    assert bob.patch(f"/api/books/{book_id}", json={"category_id": econ["id"]}).status_code == 404


# ---------------------------------------------------------------- shelf semantics

def test_own_books_are_on_the_shelf_and_public_ones_only_after_adding(people, test_engine: Engine) -> None:
    alice, bob, admin = people
    _upload(alice, "a.txt", "Một câu. Hai câu.".encode(), title="Của Alice")
    public = _upload(admin, "p.txt", "Ba câu. Bốn câu.".encode(), title="Sách hệ thống", is_public="true").json()["book_id"]
    assert _titles(alice.get("/api/books")) == ["Của Alice"]
    explore = alice.get("/api/books/explore").json()
    assert [(b["title"], b["on_shelf"]) for b in explore] == [("Sách hệ thống", False)]

    assert alice.post(f"/api/books/{public}/shelf").status_code == 204
    assert sorted(_titles(alice.get("/api/books"))) == ["Của Alice", "Sách hệ thống"]
    assert alice.get("/api/books/explore").json()[0]["on_shelf"] is True
    assert _titles(bob.get("/api/books")) == []  # Bob's shelf is his own
    assert _titles(alice.get("/api/books?source=system")) == ["Sách hệ thống"]
    assert _titles(alice.get("/api/books?source=mine")) == ["Của Alice"]

    assert alice.delete(f"/api/books/{public}/shelf").status_code == 204
    assert _titles(alice.get("/api/books")) == ["Của Alice"]


def test_the_catalogue_lists_only_public_books_and_cannot_add_private_ones(people) -> None:
    alice, bob, admin = people
    private = _upload(alice, "a.txt", "Một câu. Hai câu.".encode(), title="Riêng").json()["book_id"]
    _upload(admin, "p.txt", "Ba câu. Bốn câu.".encode(), title="Chung", is_public="true")
    assert _titles(bob.get("/api/books/explore")) == ["Chung"]
    assert _titles(alice.get("/api/books/explore")) == ["Chung"]  # not even her own private book
    assert bob.post(f"/api/books/{private}/shelf").status_code == 404
    assert alice.delete(f"/api/books/{private}/shelf").status_code == 400  # own book: delete it instead
    assert _titles(bob.get("/api/books/explore?q=chung")) == ["Chung"]
    assert _titles(bob.get("/api/books/explore?q=riêng")) == []


def test_status_follows_reading_and_can_be_set_by_hand(people) -> None:
    alice, _, _ = people
    book_id = _upload(alice, "a.txt", "Một câu. Hai câu. Ba câu. Bốn câu.".encode(), title="Sách").json()["book_id"]
    state = lambda: alice.get("/api/books").json()[0]["progress"]  # noqa: E731
    assert state() is None  # never opened
    assert alice.get("/api/books/counts").json() == {"unread": 1, "reading": 0, "completed": 0, "favorite": 0}

    alice.post("/api/bookmarks", json={"book_id": book_id, "current_sentence_index": 1, "completion_percentage": 50.0})
    assert state()["status"] == "reading" and state()["completion_percentage"] == 50.0
    alice.post("/api/bookmarks", json={"book_id": book_id, "current_sentence_index": 3, "completion_percentage": 100.0})
    assert state()["status"] == "completed"
    alice.post("/api/bookmarks", json={"book_id": book_id, "current_sentence_index": 0, "completion_percentage": 25.0})
    assert state()["status"] == "reading"  # listening again from the start

    assert alice.put(f"/api/books/{book_id}/status", json={"status": "completed"}).status_code == 204
    assert state()["status"] == "completed" and state()["completion_percentage"] == 100.0
    assert alice.get(f"/api/bookmarks/{book_id}").json()["current_sentence_index"] == 3
    assert alice.put(f"/api/books/{book_id}/status", json={"status": "unread"}).status_code == 204
    assert state()["status"] == "unread" and alice.get(f"/api/bookmarks/{book_id}").json()["current_sentence_index"] == 0
    assert alice.put(f"/api/books/{book_id}/status", json={"status": "reading"}).status_code == 400


def test_tabs_counts_and_favorites_are_independent_of_status(people) -> None:
    alice, _, admin = people
    ids = [_upload(alice, f"{i}.txt", f"Câu {i} một. Câu {i} hai.".encode(), title=f"Sách {i}").json()["book_id"] for i in range(3)]
    alice.post("/api/bookmarks", json={"book_id": ids[0], "current_sentence_index": 0, "completion_percentage": 30.0})
    alice.put(f"/api/books/{ids[1]}/status", json={"status": "completed"})
    alice.put(f"/api/books/{ids[0]}/favorite", json={"is_favorite": True})  # a reading book that is also a favourite
    alice.put(f"/api/books/{ids[2]}/favorite", json={"is_favorite": True})

    assert alice.get("/api/books/counts").json() == {"unread": 1, "reading": 1, "completed": 1, "favorite": 2}
    assert _titles(alice.get("/api/books?status=reading")) == ["Sách 0"]
    assert _titles(alice.get("/api/books?status=unread")) == ["Sách 2"]
    assert _titles(alice.get("/api/books?status=completed")) == ["Sách 1"]
    assert sorted(_titles(alice.get("/api/books?status=favorite"))) == ["Sách 0", "Sách 2"]
    assert alice.get("/api/books?status=nope").status_code == 400
    alice.put(f"/api/books/{ids[0]}/favorite", json={"is_favorite": False})
    assert alice.get("/api/books/counts").json()["favorite"] == 1
    assert alice.get("/api/books/counts?q=sach 1").json() == {"unread": 0, "reading": 0, "completed": 1, "favorite": 0}


def test_favouriting_a_public_book_puts_it_on_the_shelf(people) -> None:
    alice, bob, admin = people
    public = _upload(admin, "p.txt", "Ba câu. Bốn câu.".encode(), title="Chung", is_public="true").json()["book_id"]
    assert alice.put(f"/api/books/{public}/favorite", json={"is_favorite": True}).status_code == 204
    assert _titles(alice.get("/api/books?status=favorite")) == ["Chung"]
    assert _titles(bob.get("/api/books?status=favorite")) == []
    private = _upload(alice, "a.txt", "Một câu. Hai câu.".encode(), title="Riêng").json()["book_id"]
    assert bob.put(f"/api/books/{private}/favorite", json={"is_favorite": True}).status_code == 404
    assert bob.put(f"/api/books/{private}/status", json={"status": "completed"}).status_code == 404


def test_sorting(people) -> None:
    alice, _, _ = people
    first = _upload(alice, "1.txt", "Một câu. Hai câu.".encode(), title="Bình").json()["book_id"]
    _upload(alice, "2.txt", "Ba câu. Bốn câu.".encode(), title="An")
    third = _upload(alice, "3.txt", "Năm câu. Sáu câu.".encode(), title="Cúc").json()["book_id"]
    alice.post("/api/bookmarks", json={"book_id": first, "current_sentence_index": 0, "completion_percentage": 90.0})
    alice.post("/api/bookmarks", json={"book_id": third, "current_sentence_index": 0, "completion_percentage": 10.0})
    assert _titles(alice.get("/api/books?sort=title")) == ["An", "Bình", "Cúc"]
    assert _titles(alice.get("/api/books?sort=newest")) == ["Cúc", "An", "Bình"]
    assert _titles(alice.get("/api/books?sort=progress"))[:2] == ["Bình", "Cúc"]
    assert _titles(alice.get("/api/books?sort=recent"))[-1] == "An"  # never read: last
    assert alice.get("/api/books?sort=nope").status_code == 400


# ---------------------------------------------------------------- covers

def test_every_book_gets_a_cover_that_anyone_can_fetch(people) -> None:
    alice, _, _ = people
    book = _upload(alice, "a.txt", "Một câu. Hai câu.".encode(), title="Có bìa").json()
    url = alice.get(f"/api/books/{book['book_id']}").json()["cover_url"]
    assert url.startswith("/api/covers/") and url.endswith(".jpg")
    anonymous = TestClient(alice.app)  # <img> tags carry no token
    response = anonymous.get(url)
    assert response.status_code == 200 and response.headers["content-type"] == "image/jpeg"
    image = Image.open(io.BytesIO(response.content))
    assert image.size == (COVER_WIDTH, COVER_HEIGHT)


def test_cover_urls_cannot_be_used_to_read_other_files(people) -> None:
    alice, _, _ = people
    anonymous = TestClient(alice.app)
    for name in ("../../etc/passwd", "..%2F..%2Fsecret.jpg", "x.jpg", "a" * 32 + ".png", ("a" * 32).upper() + ".jpg", "a" * 32 + ".jpg"):
        assert anonymous.get(f"/api/covers/{name}").status_code == 404, name
    assert cover_path("../x.jpg") is None


def test_a_pdf_uses_its_first_page_as_the_cover(people) -> None:
    alice, _, _ = people
    pdf = build_pdf([["Trang bia cuon sach", "Tac gia nao do."], ["Noi dung trang hai."]])
    book = _upload(alice, "sach.pdf", pdf, title="PDF").json()
    url = alice.get(f"/api/books/{book['book_id']}").json()["cover_url"]
    image = Image.open(io.BytesIO(TestClient(alice.app).get(url).content))
    assert image.size == (COVER_WIDTH, COVER_HEIGHT)
    pixels = list(image.convert("L").getdata())
    assert sum(1 for p in pixels if p > 240) > len(pixels) * 0.7  # a white page with a little black text, not a colour gradient


def test_a_broken_pdf_cover_falls_back_to_a_generated_one() -> None:
    from src.core.ingestion.covers import render_pdf_cover

    assert render_pdf_cover("/nonexistent/file.pdf") is None


def test_uploading_a_custom_cover_at_ingest_and_replacing_it(people) -> None:
    alice, bob, _ = people
    book = _upload_with_cover(alice, _png(900, 300, "blue")).json()
    detail = alice.get(f"/api/books/{book['book_id']}").json()
    first = Path(detail["cover_url"]).name
    image = Image.open(io.BytesIO(TestClient(alice.app).get(detail["cover_url"]).content))
    assert image.size == (COVER_WIDTH, COVER_HEIGHT) and image.format == "JPEG"
    assert image.getpixel((200, 266))[2] > 150  # still the blue picture, cropped to 3:4

    replaced = alice.put(f"/api/books/{book['book_id']}/cover", files={"file": ("c.png", _png(300, 900, "green"))})
    assert replaced.status_code == 200 and Path(replaced.json()["cover_url"]).name != first
    assert cover_path(first) is None  # the old file is gone
    assert bob.put(f"/api/books/{book['book_id']}/cover", files={"file": ("c.png", _png())}).status_code == 404


def _upload_with_cover(client: TestClient, image: bytes, text: str = "Một câu. Hai câu."):
    return client.post(
        "/api/books/ingest",
        files={"file": ("a.txt", io.BytesIO(text.encode())), "cover": ("c.png", io.BytesIO(image))},
        data={"title": "Bìa riêng"},
    )


def test_bad_cover_uploads_are_refused(people) -> None:
    alice, _, _ = people
    book_id = _upload(alice, "a.txt", "Một câu. Hai câu.".encode(), title="Sách").json()["book_id"]
    for name, data in (("x.png", b"not an image"), ("x.gif", _gif()), ("big.png", b"\x89PNG" + b"0" * (2 * 1024 * 1024 + 10))):
        response = alice.put(f"/api/books/{book_id}/cover", files={"file": (name, data)})
        assert response.status_code == 400, name
    assert _upload_with_cover(alice, b"nope", "Một nội dung hoàn toàn khác. Câu hai.").status_code == 400  # a bad cover must not create half a book
    assert len(alice.get("/api/books").json()) == 1


def _gif() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buffer, "GIF")
    return buffer.getvalue()


def test_deleting_a_book_deletes_its_cover_file(people) -> None:
    alice, _, _ = people
    book = _upload(alice, "a.txt", "Một câu. Hai câu.".encode(), title="Sẽ xóa").json()
    name = Path(alice.get(f"/api/books/{book['book_id']}").json()["cover_url"]).name
    assert cover_path(name) is not None
    assert alice.delete(f"/api/books/{book['book_id']}").status_code == 204
    assert cover_path(name) is None


def test_cover_helpers() -> None:
    jpeg = generate_default_cover("Đắc Nhân Tâm: một tên sách rất dài " * 3, "Dale Carnegie")
    assert Image.open(io.BytesIO(jpeg)).size == (COVER_WIDTH, COVER_HEIGHT)
    assert normalize_uploaded_cover(_png(100, 100)).startswith(b"\xff\xd8")  # tiny images are scaled up
    with pytest.raises(CoverError):
        normalize_uploaded_cover(b"")
    with pytest.raises(CoverError):
        normalize_uploaded_cover(_gif())
    assert cover_dir().is_dir()


# ---------------------------------------------------------------- books from before these features

def test_older_books_get_search_text_and_a_cover_at_start(test_engine: Engine) -> None:
    with test_engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO books (title, author, source_path, content_hash, owner_id) VALUES ('Sách Cũ', 'Tác Giả', 'x', :h, 1)"),
            {"h": "9" * 64})
    run_migrations(test_engine)
    with test_engine.connect() as conn:
        search, cover = conn.execute(text("SELECT search_text, cover_path FROM books")).fetchone()
    assert search == "sach cu tac gia" and cover and cover_path(cover) is not None
    backfill_book_extras(test_engine)  # running again changes nothing
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT cover_path FROM books")).scalar() == cover


def test_existing_database_gets_the_new_tags_once(test_engine: Engine) -> None:
    from src.core.storage.library import (
        CATEGORIES_FLAG,
        DEFAULT_CATEGORIES,
        ensure_default_categories,
    )

    old_six = ["tieu-thuyet", "ky-nang-song", "cong-nghe", "kinh-te", "truyen-ngan", "khac"]
    with test_engine.begin() as conn:
        conn.execute(text("DELETE FROM categories"))
        conn.execute(text("DELETE FROM app_settings WHERE setting_key = :k"), {"k": CATEGORIES_FLAG})
        for order, (name, slug, icon, color) in enumerate(c for c in DEFAULT_CATEGORIES if c[1] in old_six):
            conn.execute(text("INSERT INTO categories (name, slug, icon, color, sort_order) VALUES (:n, :s, :i, :c, :o)"),
                         {"n": name, "s": slug, "i": icon, "c": color, "o": order})
    ensure_default_categories(test_engine)
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM categories")).scalar() == 15
    with test_engine.begin() as conn:
        conn.execute(text("DELETE FROM categories WHERE slug = 'kinh-di'"))  # an admin removed a tag
    ensure_default_categories(test_engine)  # a later start must not bring it back
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM categories")).scalar() == 14
