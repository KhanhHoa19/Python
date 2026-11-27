"""Table of contents: chapter titles stored at ingestion, outline hints from PDF/DOCX, backfill, cascade."""

from __future__ import annotations

import io
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from src.core.ingestion.parser import normalize_heading, split_into_chapters_and_sentences
from src.core.ingestion.service import IngestionService
from src.core.storage.repositories import SqlBookRepository
from tests.integration.test_api_extended import add_book, client, provider  # noqa: F401
from tests.pdf_helpers import build_pdf


def _upload(client: TestClient, name: str, data: bytes) -> dict:  # noqa: F811
    resp = client.post("/api/books/ingest", files={"file": (name, io.BytesIO(data))})
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------- parser hints

def test_normalize_heading_ignores_case_spaces_and_edge_punctuation() -> None:
    assert normalize_heading("  Giới   Thiệu: ") == "giới thiệu"
    assert normalize_heading("PHẦN MỞ ĐẦU.") == "phần mở đầu"


def test_outline_hint_starts_a_chapter_when_the_regex_would_not() -> None:
    body = "Giới thiệu\nXin chào các bạn. Đây là phần đầu.\n\nKết luận\nCảm ơn đã nghe. Hẹn gặp lại.\n"
    assert len(split_into_chapters_and_sentences(body)) == 1  # no "Chương N": one block
    chapters = split_into_chapters_and_sentences(body, heading_hints=["GIỚI THIỆU", "kết luận"])
    assert [c["title"] for c in chapters] == ["Giới thiệu", "Kết luận"]
    assert chapters[0]["sentences"][0] == "Xin chào các bạn."


def test_hint_must_equal_the_whole_line() -> None:
    body = "Mở đầu\nCâu thứ nhất của chương này. Tiếp theo là kết luận của tác giả về vấn đề.\n"
    chapters = split_into_chapters_and_sentences(body, heading_hints=["kết luận"])
    assert len(chapters) == 1  # "kết luận" only appears inside a sentence


# ---------------------------------------------------------------- ingestion + endpoint

def test_ingest_stores_chapter_titles_and_ranges(client: TestClient) -> None:  # noqa: F811
    md = ("Lời tựa ngắn.\n\n# Chương 1: Khởi đầu\nMột câu. Hai câu.\n\n# Chương 2: Hành trình\nBa câu. Bốn câu. Năm câu.\n")
    book = _upload(client, "sach.md", md.encode())
    body = client.get(f"/api/books/{book['book_id']}/chapters").json()
    chapters = body["chapters"]
    assert [c["title"] for c in chapters] == ["Mở đầu", "Chương 1: Khởi đầu", "Chương 2: Hành trình"]
    assert [(c["start_sentence_index"], c["end_sentence_index"]) for c in chapters] == [(0, 0), (1, 2), (3, 5)]
    assert [c["sentence_count"] for c in chapters] == [1, 2, 3]
    assert chapters[2]["word_count"] > 0 and [c["chapter_index"] for c in chapters] == [1, 2, 3]
    sentences = client.get(f"/api/books/{book['book_id']}/sentences").json()["sentences"]
    assert sentences[3]["chapter_index"] == 3  # sentence and chapter numbering agree


def test_document_without_headings_is_one_whole_chapter(client: TestClient) -> None:  # noqa: F811
    book = _upload(client, "ngan.txt", "Một câu. Hai câu. Ba câu.".encode())
    chapters = client.get(f"/api/books/{book['book_id']}/chapters").json()["chapters"]
    assert [c["title"] for c in chapters] == ["Toàn bộ tài liệu"]


def test_chapters_of_an_older_book_are_rebuilt_once(client: TestClient, test_engine: Engine) -> None:  # noqa: F811
    book_id = add_book(test_engine, ["Một.", "Hai.", "Ba."])  # saved without chapter rows, like books ingested earlier
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM document_chapters")).scalar() == 0
    chapters = client.get(f"/api/books/{book_id}/chapters").json()["chapters"]
    assert [(c["title"], c["start_sentence_index"], c["end_sentence_index"]) for c in chapters] == [("Chương 1", 0, 2)]
    assert client.get(f"/api/books/{book_id}/chapters").json()["chapters"] == chapters
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM document_chapters")).scalar() == 1


def test_chapters_of_a_missing_book_is_404(client: TestClient) -> None:  # noqa: F811
    assert client.get("/api/books/999/chapters").status_code == 404


def test_deleting_a_book_deletes_its_chapters(client: TestClient, test_engine: Engine) -> None:  # noqa: F811
    book = _upload(client, "x.md", b"# Chuong 1\nMot cau. Hai cau.\n# Chuong 2\nBa cau.\n")
    assert client.delete(f"/api/books/{book['book_id']}").status_code == 204
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM document_chapters")).scalar() == 0


# ---------------------------------------------------------------- outlines of real files

def test_pdf_bookmarks_become_chapters(client: TestClient, tmp_path: Path) -> None:  # noqa: F811
    from pypdf import PdfReader, PdfWriter

    plain = tmp_path / "plain.pdf"
    plain.write_bytes(build_pdf([
        ["Getting Started", "First sentence of the book.", "Second sentence of the book."],
        ["Going Further", "Third sentence of the book.", "Fourth sentence of the book."],
    ]))
    writer = PdfWriter(clone_from=PdfReader(str(plain)))
    writer.add_outline_item("Getting Started", 0)
    writer.add_outline_item("Going Further", 1)
    with_outline = tmp_path / "outline.pdf"
    with open(with_outline, "wb") as handle:
        writer.write(handle)

    book = _upload(client, "outline.pdf", with_outline.read_bytes())
    chapters = client.get(f"/api/books/{book['book_id']}/chapters").json()["chapters"]
    assert [c["title"] for c in chapters] == ["Getting Started", "Going Further"]
    assert chapters[0]["end_sentence_index"] + 1 == chapters[1]["start_sentence_index"]

    other = tmp_path / "other.pdf"  # the same kind of text without bookmarks (different text: same text would be a duplicate)
    other.write_bytes(build_pdf([["Alpha beta", "Only one sentence here.", "Another sentence here."]]))
    plain_book = _upload(client, "other.pdf", other.read_bytes())
    assert len(client.get(f"/api/books/{plain_book['book_id']}/chapters").json()["chapters"]) == 1


def test_a_single_top_level_bookmark_is_read_one_level_deeper() -> None:
    from src.core.ingestion.reader import _outline_titles

    class Item:
        def __init__(self, title: str) -> None:
            self.title = title

    class Fake:
        outline = [Item("The Whole Book"), [Item("Part One"), Item("Part Two")]]

    assert _outline_titles(Fake()) == ["Part One", "Part Two"]

    class Broken:
        @property
        def outline(self) -> list:
            raise KeyError("/Outlines")

    assert _outline_titles(Broken()) == []


def test_docx_heading_1_becomes_a_chapter(client: TestClient) -> None:  # noqa: F811
    from docx import Document

    doc = Document()
    doc.add_paragraph("Phần dẫn nhập của cuốn sách.")
    doc.add_heading("Giới thiệu", level=1)
    doc.add_paragraph("Đây là câu đầu tiên. Đây là câu thứ hai.")
    doc.add_heading("Kết luận", level=1)
    doc.add_paragraph("Hẹn gặp lại các bạn.")
    buffer = io.BytesIO()
    doc.save(buffer)
    book = _upload(client, "word.docx", buffer.getvalue())
    titles = [c["title"] for c in client.get(f"/api/books/{book['book_id']}/chapters").json()["chapters"]]
    assert titles == ["Mở đầu", "Giới thiệu", "Kết luận"]


def test_service_saves_chapters_in_the_same_transaction(test_engine: Engine, tmp_path: Path) -> None:
    path = tmp_path / "b.md"
    path.write_text("# Chương 1\nMột câu.\n# Chương 2\nHai câu.\n", encoding="utf-8")
    book = IngestionService(book_repo=SqlBookRepository(test_engine)).ingest_file(path, title="B")
    chapters = SqlBookRepository(test_engine).get_chapters(book.id or 0)
    assert [c.title for c in chapters] == ["Chương 1", "Chương 2"]
