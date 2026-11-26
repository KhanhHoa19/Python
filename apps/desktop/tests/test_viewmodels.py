"""Pure view-model helpers."""

from __future__ import annotations

from ui.viewmodels import (
    describe_voice,
    filter_and_sort_books,
    format_datetime,
    format_minutes,
    format_number,
    most_recent_unfinished,
    normalize_text,
    usage_ratio,
)


def book(title: str, pct: float | None = None, last: str | None = None, created: str = "2026-01-01T00:00:00", author: str = "") -> dict:
    data = {"id": 1, "title": title, "author": author, "created_at": created}
    if pct is not None:
        data["bookmark"] = {"completion_percentage": pct, "last_read_at": last}
    return data


def test_normalize_strips_vietnamese_accents_and_case() -> None:
    assert normalize_text("Đại Học Bách Khoa") == "dai hoc bach khoa"


def test_search_ignores_accents() -> None:
    books = [book("Cấu trúc dữ liệu"), book("Giáo trình Python")]
    result = filter_and_sort_books(books, "cau truc", "Tên A→Z")
    assert [b["title"] for b in result] == ["Cấu trúc dữ liệu"]


def test_search_matches_author() -> None:
    assert len(filter_and_sort_books([book("A", author="Nguyễn Văn An")], "van an", "Tên A→Z")) == 1


def test_sort_by_recent_puts_unread_last() -> None:
    books = [book("never"), book("old", 10, "2026-01-02T10:00:00"), book("new", 10, "2026-03-02T10:00:00")]
    assert [b["title"] for b in filter_and_sort_books(books, "", "Đọc gần đây")] == ["new", "old", "never"]


def test_sort_by_progress_and_added_date() -> None:
    books = [book("a", 10, created="2026-01-01T00:00:00"), book("b", 90, created="2026-02-01T00:00:00")]
    assert filter_and_sort_books(books, "", "Tiến độ")[0]["title"] == "b"
    assert filter_and_sort_books(books, "", "Ngày thêm")[0]["title"] == "b"


def test_most_recent_unfinished_skips_new_and_finished() -> None:
    books = [
        book("new"), book("done", 100, "2026-05-01T00:00:00"),
        book("a", 20, "2026-02-01T00:00:00"), book("b", 50, "2026-04-01T00:00:00"),
    ]
    assert most_recent_unfinished(books)["title"] == "b"
    assert most_recent_unfinished([book("new"), book("done", 100, "2026-05-01T00:00:00")]) is None


def test_formatting() -> None:
    assert format_minutes(760) == "12 giờ 40" and format_minutes(35) == "35 phút"
    assert format_minutes(0.2) == "12 giây" and format_minutes(0) == "0 phút"
    assert format_number(96200) == "96.200"
    assert format_datetime("2026-11-25T21:10:00Z") == "25/11/2026 21:10" and format_datetime(None) == "—"


def test_describe_voice() -> None:
    label = describe_voice({"display_name": "Hoài My", "gender": "female", "style": "kể chuyện"})
    assert label == "Hoài My · Nữ · kể chuyện"
    assert describe_voice({"display_name": "Tôi", "is_custom": True}).endswith("Giọng của tôi")


def test_usage_ratio() -> None:
    assert usage_ratio(25, 100) == 0.25 and usage_ratio(500, 100) == 1.0 and usage_ratio(10, 0) == 0.0
