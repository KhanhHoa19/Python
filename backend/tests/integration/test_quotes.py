"""Favourite quotes: one-tap bookmarks, feelings, context, permanent audio, playlists' data and cleanup."""

from __future__ import annotations

import io
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from src.core.audio.quotes import EMOTION_TAGS, delete_quote_audio, quote_audio_path, quotes_root
from src.core.config import get_settings
from src.core.player.audio_service import QuotaExceededError
from tests.auth_helpers import make_user, sign_in, user_by_name
from tests.integration.test_accounts import app  # noqa: F401  (fixture)
from tests.integration.test_api_extended import provider  # noqa: F401

SENTENCES = ["Câu thứ nhất của sách.", "Câu thứ hai rất hay.", "Câu thứ ba kết thúc."]


@pytest.fixture
def reader(app: TestClient, test_engine: Engine):  # noqa: F811
    alice = sign_in(TestClient(app.app), test_engine, make_user(test_engine, "alice"))
    bob = sign_in(TestClient(app.app), test_engine, make_user(test_engine, "bob"))
    uploaded = alice.post("/api/books/ingest", files={"file": ("s.txt", io.BytesIO(" ".join(SENTENCES).encode()))},
                          data={"title": "Sách trích dẫn"})
    assert uploaded.status_code == 201
    return alice, bob, uploaded.json()["book_id"]


def _tap(client: TestClient, book_id: int, index: int = 1, **extra):
    return client.post("/api/notes", json={"book_id": book_id, "sentence_index": index, **extra})


# ---------------------------------------------------------------- one tap

def test_one_tap_saves_the_whole_sentence_with_context_and_audio(reader) -> None:
    alice, _, book_id = reader
    response = _tap(alice, book_id, 1)
    assert response.status_code == 201
    quote = response.json()
    assert quote["excerpt"] == SENTENCES[1]
    assert (quote["start_offset"], quote["end_offset"]) == (0, len(SENTENCES[1]))
    assert quote["context_before"] == SENTENCES[0] and quote["context_after"] == SENTENCES[2]
    assert quote["has_audio"] is True and quote["emotion_tag"] is None and quote["note_text"] == ""
    assert "audio_path" not in quote  # a server path is never sent out
    stored = list((quotes_root() / str(user_by_name_id(alice))).glob("*"))
    assert len(stored) == 1 and stored[0].stat().st_size > 0


def user_by_name_id(client: TestClient) -> int:
    return client.get("/api/auth/me").json()["id"]


def test_first_and_last_sentences_have_one_sided_context(reader) -> None:
    alice, _, book_id = reader
    first = _tap(alice, book_id, 0).json()
    last = _tap(alice, book_id, 2).json()
    assert first["context_before"] == "" and first["context_after"] == SENTENCES[1]
    assert last["context_before"] == SENTENCES[1] and last["context_after"] == ""


def test_tapping_twice_keeps_one_quote_and_can_add_the_feeling(reader) -> None:
    alice, _, book_id = reader
    first = _tap(alice, book_id, 1)
    again = _tap(alice, book_id, 1, emotion_tag="wise")
    assert first.status_code == 201 and again.status_code == 200
    assert again.json()["id"] == first.json()["id"] and again.json()["emotion_tag"] == "wise"
    assert len(alice.get("/api/notes").json()) == 1


def test_a_selected_part_is_a_quote_too_and_both_offsets_are_needed(reader) -> None:
    alice, _, book_id = reader
    part = _tap(alice, book_id, 1, start_offset=0, end_offset=8, note_text="ghi nhớ", emotion_tag="touching").json()
    assert part["excerpt"] == SENTENCES[1][:8] and part["note_text"] == "ghi nhớ" and part["has_audio"]
    assert _tap(alice, book_id, 1, start_offset=3).status_code == 400
    assert _tap(alice, book_id, 1, end_offset=3).status_code == 400
    assert _tap(alice, book_id, 1, start_offset=5, end_offset=5).status_code == 400
    assert _tap(alice, book_id, 1, start_offset=0, end_offset=999).status_code == 400
    assert _tap(alice, book_id, 99).status_code == 404
    assert len(alice.get("/api/notes").json()) == 1  # a part and the whole sentence would be two different quotes


def test_the_four_feelings(reader) -> None:
    alice, _, book_id = reader
    assert set(EMOTION_TAGS) == {"inspiring", "touching", "wise", "funny"}
    for index, tag in enumerate(EMOTION_TAGS):
        assert _tap(alice, book_id, index % 3, start_offset=0, end_offset=index + 2, emotion_tag=tag).json()["emotion_tag"] == tag
    assert _tap(alice, book_id, 0, emotion_tag="angry").status_code == 400


# ---------------------------------------------------------------- filtering and editing

def test_filter_by_feeling_and_book(reader) -> None:
    alice, _, book_id = reader
    other = alice.post("/api/books/ingest", files={"file": ("o.txt", io.BytesIO("Một sách khác hẳn. Câu hai khác.".encode()))},
                       data={"title": "Sách khác"}).json()["book_id"]
    _tap(alice, book_id, 0, emotion_tag="funny")
    _tap(alice, book_id, 1, emotion_tag="wise")
    _tap(alice, other, 0, emotion_tag="wise")
    assert len(alice.get("/api/notes").json()) == 3
    assert {n["emotion_tag"] for n in alice.get("/api/notes?emotion_tag=wise").json()} == {"wise"}
    assert len(alice.get("/api/notes?emotion_tag=wise").json()) == 2
    assert len(alice.get(f"/api/notes?book_id={book_id}").json()) == 2
    assert len(alice.get(f"/api/notes?book_id={book_id}&emotion_tag=wise").json()) == 1
    assert alice.get("/api/notes?emotion_tag=nope").status_code == 400


def test_editing_the_text_and_the_feeling(reader) -> None:
    alice, _, book_id = reader
    note_id = _tap(alice, book_id, 1).json()["id"]
    edited = alice.patch(f"/api/notes/{note_id}", json={"emotion_tag": "inspiring", "note_text": "để dành"}).json()
    assert (edited["emotion_tag"], edited["note_text"]) == ("inspiring", "để dành")
    assert alice.patch(f"/api/notes/{note_id}", json={"note_text": "chỉ đổi chữ"}).json()["emotion_tag"] == "inspiring"
    assert alice.patch(f"/api/notes/{note_id}", json={"emotion_tag": None}).json()["emotion_tag"] is None  # cleared
    assert alice.patch(f"/api/notes/{note_id}", json={}).status_code == 400
    assert alice.patch(f"/api/notes/{note_id}", json={"emotion_tag": "bad"}).status_code == 400
    assert alice.patch("/api/notes/9999", json={"note_text": "x"}).status_code == 404


# ---------------------------------------------------------------- the saved audio

def test_the_saved_audio_survives_clearing_the_cache(reader) -> None:
    alice, _, book_id = reader
    note_id = _tap(alice, book_id, 1).json()["id"]
    cache = Path(get_settings().audio_cache_dir)
    shutil.rmtree(cache, ignore_errors=True)  # "dọn bộ nhớ đệm"
    response = alice.get(f"/api/notes/{note_id}/audio")
    assert response.status_code == 200 and response.headers["content-type"].startswith("audio/") and len(response.content) > 100
    assert not cache.exists() or not any(cache.rglob("*.*"))  # served from the saved copy, nothing re-synthesised


def test_a_lost_audio_file_is_made_again_on_demand(reader) -> None:
    alice, _, book_id = reader
    note_id = _tap(alice, book_id, 1).json()["id"]
    for path in quotes_root().rglob("*.*"):
        path.unlink()
    assert alice.get("/api/notes").json()[0]["has_audio"] is False
    assert alice.get(f"/api/notes/{note_id}/audio").status_code == 200
    assert alice.get("/api/notes").json()[0]["has_audio"] is True  # saved again for next time


def test_a_quote_is_saved_even_when_the_audio_cannot_be_made(reader) -> None:
    alice, _, book_id = reader
    with patch("src.api.routes.notes.get_or_create_audio", side_effect=QuotaExceededError("limit")):
        response = _tap(alice, book_id, 1)
    assert response.status_code == 201 and response.json()["has_audio"] is False
    assert alice.get(f"/api/notes/{response.json()['id']}/audio").status_code == 200  # made at the first play instead


def test_stored_audio_paths_cannot_escape_the_quotes_folder(tmp_path) -> None:
    outside = tmp_path / "secret.mp3"
    outside.write_bytes(b"secret")
    for bad in ("../secret.mp3", "../../secret.mp3", str(outside), "", None, "../" + outside.name):
        assert quote_audio_path(bad) is None
    delete_quote_audio("../secret.mp3")
    assert outside.exists()


def test_deleting_a_quote_deletes_its_audio_and_deleting_the_book_deletes_everyones(reader) -> None:
    alice, bob, book_id = reader
    first = _tap(alice, book_id, 0).json()["id"]
    _tap(alice, book_id, 1)
    files = lambda: list(quotes_root().rglob("*.*"))  # noqa: E731
    assert len(files()) == 2
    assert alice.delete(f"/api/notes/{first}").status_code == 204
    assert len(files()) == 1
    assert alice.delete(f"/api/books/{book_id}").status_code == 204
    assert files() == [] and alice.get("/api/notes").json() == []


# ---------------------------------------------------------------- privacy

def test_quotes_are_private(reader) -> None:
    alice, bob, book_id = reader
    note_id = _tap(alice, book_id, 1, emotion_tag="wise").json()["id"]
    assert bob.get("/api/notes").json() == []
    assert bob.get(f"/api/notes/{note_id}/audio").status_code == 404
    assert bob.patch(f"/api/notes/{note_id}", json={"emotion_tag": "funny"}).status_code == 404
    assert bob.delete(f"/api/notes/{note_id}").status_code == 404
    assert _tap(bob, book_id, 1).status_code == 404  # Bob cannot even see Alice's private book
    assert alice.get("/api/notes").json()[0]["emotion_tag"] == "wise"


def test_quoting_a_public_book_is_personal(app: TestClient, test_engine: Engine) -> None:  # noqa: F811
    admin = sign_in(TestClient(app.app), test_engine, user_by_name(test_engine, "admin"))
    carol = sign_in(TestClient(app.app), test_engine, make_user(test_engine, "carol"))
    dave = sign_in(TestClient(app.app), test_engine, make_user(test_engine, "dave"))
    book = admin.post("/api/books/ingest", files={"file": ("p.txt", io.BytesIO(" ".join(SENTENCES).encode()))},
                      data={"title": "Chung", "is_public": "true"}).json()["book_id"]
    assert _tap(carol, book, 1, emotion_tag="touching").status_code == 201
    assert _tap(dave, book, 1).json()["emotion_tag"] is None  # the same sentence, Dave's own quote
    assert len(carol.get("/api/notes").json()) == len(dave.get("/api/notes").json()) == 1
    assert (quotes_root() / "1").exists() is False
    folders = sorted(p.name for p in quotes_root().iterdir())
    assert len(folders) == 2  # one folder per person


# ---------------------------------------------------------------- notes made before quotes existed

def test_an_older_note_gets_the_new_columns_and_its_audio_on_first_play(reader, test_engine: Engine) -> None:
    alice, _, book_id = reader
    user_id = user_by_name_id(alice)
    with test_engine.begin() as conn:
        conn.execute(text("INSERT INTO audio_notes (user_id, book_id, sentence_index, start_offset, end_offset, note_text) "
                          "VALUES (:u, :b, 0, 0, 8, 'cũ')"), {"u": user_id, "b": book_id})
    old = alice.get("/api/notes").json()[0]
    assert old["note_text"] == "cũ" and old["emotion_tag"] is None and old["has_audio"] is False
    assert old["context_before"] == "" and old["voice"] is None
    assert alice.get(f"/api/notes/{old['id']}/audio").status_code == 200
