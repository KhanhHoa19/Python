"""Pure view-model helpers."""

from __future__ import annotations

from ui.viewmodels import (
    check_book_title,
    describe_voice,
    format_datetime,
    format_minutes,
    format_number,
    most_recent_unfinished,
    normalize_text,
    pick_initial_tab,
    play_label,
    progress_fraction,
    usage_ratio,
)


def book(title: str, pct: float | None = None, last: str | None = None, created: str = "2026-01-01T00:00:00", author: str = "") -> dict:
    data = {"id": 1, "title": title, "author": author, "created_at": created}
    if pct is not None:
        data["progress"] = {"completion_percentage": pct, "last_read_at": last}
    return data


def test_normalize_strips_vietnamese_accents_and_case() -> None:
    assert normalize_text("Đại Học Bách Khoa") == "dai hoc bach khoa"


def test_progress_fraction_is_clamped() -> None:
    assert progress_fraction(None) == 0.0
    assert progress_fraction({"completion_percentage": 42.5}) == 0.425
    assert progress_fraction({"completion_percentage": 180}) == 1.0


def test_initial_shelf_tab_is_the_first_with_books() -> None:
    assert pick_initial_tab({"reading": 2, "unread": 5, "completed": 1, "favorite": 3}) == "reading"
    assert pick_initial_tab({"reading": 0, "unread": 5, "completed": 1, "favorite": 3}) == "unread"
    assert pick_initial_tab({"reading": 0, "unread": 0, "completed": 0, "favorite": 4}) == "favorite"
    assert pick_initial_tab({}) == "reading"


def test_play_label_follows_status() -> None:
    assert [play_label(s) for s in ("reading", "completed", "unread", None)] == ["Nghe tiếp", "Nghe lại", "Bắt đầu nghe", "Bắt đầu nghe"]


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


def test_check_book_title() -> None:
    assert check_book_title("  Sherlock   Holmes \n tập một ") == ("Sherlock Holmes tập một", None)
    for raw in ("", "   ", "\n\t"):
        assert check_book_title(raw)[0] is None and check_book_title(raw)[1]
    assert check_book_title("ế" * 255)[1] is None and check_book_title("ế" * 256)[0] is None


def test_cover_helpers_are_stable_and_match_the_web_app() -> None:
    from ui.viewmodels import cover_color, cover_hue, cover_initials

    assert cover_hue("Sherlock Holmes") == cover_hue("Sherlock Holmes")
    assert 0 <= cover_hue("") < 360 and 0 <= cover_hue("x" * 500) < 360
    assert len({cover_hue(t) for t in ("Một", "Hai", "Ba", "Bốn", "Năm", "Sáu")}) > 3
    assert cover_color("Đắc Nhân Tâm").startswith("#") and len(cover_color("Đắc Nhân Tâm")) == 7
    assert cover_initials("Đắc Nhân Tâm") == "ĐN"
    assert cover_initials("  sherlock   holmes  ") == "SH"
    assert cover_initials("— ...") == "♪"


def test_voice_studio_helpers() -> None:
    from ui.viewmodels import clone_quota, split_voices

    provider = {"voice_id": "p", "is_custom": False}
    shared = {"voice_id": "s", "is_custom": True, "is_public": True, "is_mine": False}
    mine = {"voice_id": "m", "is_custom": True, "is_mine": True}
    own_public = {"voice_id": "mp", "is_custom": True, "is_mine": True, "is_public": True}
    system, own = split_voices([provider, shared, mine, own_public])
    assert [v["voice_id"] for v in system] == ["p", "s"]
    assert [v["voice_id"] for v in own] == ["m", "mp"]
    assert clone_quota({"my_voice_count": 2, "max_voices": 3}) == (2, 3, False)
    assert clone_quota({"my_voice_count": 3, "max_voices": 3})[2] is True
    assert clone_quota({"my_voice_count": 8, "max_voices": None}) == (8, None, False)
    assert clone_quota(None) == (0, None, False)
    assert "Giọng chung" in describe_voice({"display_name": "A", "is_custom": True, "is_mine": False})


def test_admin_helpers() -> None:
    from ui.viewmodels import category_problem, sort_system_books

    assert "tên" in (category_problem("  ", "#112233") or "")
    assert "Màu" in (category_problem("Sử", "red") or "")
    assert category_problem("Sử", "#A1B2c3") is None
    books = [{"title": "Zeta", "is_public": False}, {"title": "Đông", "is_public": True}, {"title": "An", "is_public": True}]
    assert [b["title"] for b in sort_system_books(books)] == ["An", "Đông", "Zeta"]


def test_recommend_helpers() -> None:
    from ui.viewmodels import (
        DURATION_OPTIONS,
        describe_filters,
        format_duration,
        toggle_slug,
    )

    assert toggle_slug(["a"], "b") == ["a", "b"] and toggle_slug(["a", "b"], "a") == ["b"]
    assert [format_duration(m) for m in (0, 25, 60, 125)] == ["~1 phút", "~25 phút", "~1 giờ", "~2 giờ 5 phút"]
    assert DURATION_OPTIONS[0][1] is None
    limits = [m for _, m in DURATION_OPTIONS[1:]]
    assert limits == sorted(limits)
    assert describe_filters(None, "Bất kỳ", None) == ""
    assert describe_filters("Hồi hộp", "≤ 30 phút", 30) == "Đang lọc: tâm trạng hồi hộp, ≤ 30 phút"
