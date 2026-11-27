"""Pure helpers for the UI (no Tk imports) so they can be unit-tested."""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Any

# Shelf tabs, filters and sorting: the backend does the searching; these are only the labels shown for its values.
SHELF_TABS = (("reading", "Đang nghe dở"), ("unread", "Chưa nghe"), ("completed", "Đã hoàn thành"), ("favorite", "Yêu thích"))
SOURCE_OPTIONS = (("all", "Tất cả"), ("system", "Sách hệ thống"), ("mine", "Sách của tôi"))
SORT_OPTIONS = (("recent", "Đọc gần đây"), ("title", "Tên A→Z"), ("newest", "Ngày thêm"), ("progress", "Tiến độ"))
# The feelings a quote can carry (value, label): the same four as the web app and the backend.
EMOTIONS = (("inspiring", "Truyền cảm hứng"), ("touching", "Chạm cảm xúc"), ("wise", "Triết lý hay"), ("funny", "Hài hước"))


def emotion_label(tag: str | None) -> str:
    return next((label for value, label in EMOTIONS if value == tag), "")


def matches_quote(note: dict[str, Any], query: str) -> bool:
    """Text search inside the quotes on screen (accents and case ignored)."""
    needle = normalize_text(query.strip())
    return not needle or needle in normalize_text(f"{note['excerpt']} {note['note_text']} {note['book_title']}")


EXPLORE_SORTS = (("newest", "Mới nhất"), ("title", "Tên A→Z"))


def pick_initial_tab(counts: dict[str, int]) -> str:
    """The shelf tab to open first: the first one with books, else "reading"."""
    return next((key for key, _ in SHELF_TABS if counts.get(key, 0) > 0), "reading")


def play_label(status: str | None) -> str:
    """Text of a book card's primary button."""
    return {"reading": "Nghe tiếp", "completed": "Nghe lại"}.get(status or "", "Bắt đầu nghe")


def normalize_text(value: str) -> str:
    """Lowercase and strip Vietnamese diacritics so search ignores case and accents."""
    decomposed = unicodedata.normalize("NFD", value.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def format_datetime(value: str | None) -> str:
    """dd/mm/yyyy HH:MM, or an em dash when missing."""
    parsed = parse_iso(value)
    return parsed.strftime("%d/%m/%Y %H:%M") if parsed else "—"


def format_minutes(minutes: float) -> str:
    """'12 giờ 40' for long durations, '35 phút' for short ones, '12 giây' under a minute."""
    if 0 < minutes < 1:
        return f"{max(1, round(minutes * 60))} giây"
    total = round(minutes)
    hours, mins = divmod(total, 60)
    return f"{hours} giờ {mins:02d}" if hours else f"{mins} phút"


def format_number(value: float) -> str:
    """Thousands separated by dots: 96200 -> '96.200'."""
    return f"{round(value):,}".replace(",", ".")


def progress_fraction(progress: dict[str, Any] | None) -> float:
    """0..1 from a book's `progress` dict (None = never opened)."""
    if not progress:
        return 0.0
    return min(max(float(progress.get("completion_percentage", 0.0)) / 100.0, 0.0), 1.0)


def most_recent_unfinished(books: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The book to resume on startup: being read (0 < progress < 100%), most recently read first."""
    candidates = [
        b for b in books
        if 0.0 < progress_fraction(b.get("progress")) < 1.0 and (b.get("progress") or {}).get("last_read_at")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda b: parse_iso(b["progress"]["last_read_at"]) or datetime.min)


def describe_voice(voice: dict[str, Any]) -> str:
    """'Hoài My · Nữ · kể chuyện' style label for lists and dropdowns."""
    gender = {"female": "Nữ", "male": "Nam"}.get(str(voice.get("gender") or "").lower(), "")
    parts = [voice.get("display_name", voice.get("voice_id", "")), gender, voice.get("style") or ""]
    if voice.get("is_custom"):
        parts.append("Giọng chung" if voice.get("is_mine") is False else "Giọng của tôi")
    return " · ".join(p for p in parts if p)


def split_voices(voices: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(system voices, the user's own clones): provider voices and public clones of others vs. clones the user made."""
    system = [v for v in voices if not v.get("is_custom") or (v.get("is_public") and not v.get("is_mine"))]
    mine = [v for v in voices if v.get("is_custom") and v.get("is_mine")]
    return system, mine


def clone_quota(data: dict[str, Any] | None) -> tuple[int, int | None, bool]:
    """(voices cloned, allowed or None for unlimited, limit reached)."""
    used = int((data or {}).get("my_voice_count") or 0)
    maximum = (data or {}).get("max_voices")
    return used, maximum, maximum is not None and used >= maximum


CATEGORY_ICONS = (("book-open", "Sách mở"), ("sprout", "Mầm cây"), ("cpu", "Công nghệ"),
                  ("trending-up", "Biểu đồ"), ("feather", "Lông vũ"), ("layers", "Lớp"),
                  ("search", "Kính lúp"), ("flask-conical", "Khoa học"), ("landmark", "Di tích"), ("brain", "Bộ não"),
                  ("lightbulb", "Bóng đèn"), ("heart", "Trái tim"), ("ghost", "Bóng ma"), ("compass", "La bàn"),
                  ("baby", "Trẻ em"))


def category_problem(name: str, color: str) -> str | None:
    """Why a category form cannot be saved yet (None = fine)."""
    if not name.strip():
        return "Hãy nhập tên thể loại."
    if len(color) != 7 or color[0] != "#" or any(c not in "0123456789abcdefABCDEF" for c in color[1:]):
        return "Màu phải có dạng #a1b2c3."
    return None


def sort_system_books(books: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Public books first, then the admin's private ones; each group by title."""
    return sorted(books, key=lambda b: (not b.get("is_public"), normalize_text(b.get("title", ""))))


# Gợi Ý (S12): same options as apps/web/src/lib/recommend.ts
DURATION_OPTIONS = (("Bất kỳ", None), ("≤ 15 phút", 15), ("≤ 30 phút", 30), ("≤ 1 giờ", 60), ("≤ 3 giờ", 180))


def format_duration(minutes: int) -> str:
    """"~25 phút", "~1 giờ", "~2 giờ 5 phút"."""
    if minutes < 60:
        return f"~{max(1, minutes)} phút"
    hours, rest = divmod(minutes, 60)
    return f"~{hours} giờ" if rest == 0 else f"~{hours} giờ {rest} phút"


def toggle_slug(chosen: list[str], slug: str) -> list[str]:
    """Add the slug if missing, remove it if present (the order of picking is kept)."""
    return [s for s in chosen if s != slug] if slug in chosen else [*chosen, slug]


def describe_filters(mood_label: str | None, duration_label: str, duration_minutes: int | None) -> str:
    parts = [f"tâm trạng {mood_label.lower()}" if mood_label else "", duration_label if duration_minutes else ""]
    parts = [p for p in parts if p]
    return f"Đang lọc: {', '.join(parts)}" if parts else ""


def usage_ratio(used: int, limit: int) -> float:
    """0..1 share of the daily character limit; 0 when unlimited."""
    return min(used / limit, 1.0) if limit > 0 else 0.0


MAX_TITLE_LENGTH = 255


def check_book_title(raw: str) -> tuple[str | None, str | None]:
    """(title, error): trim, collapse inner whitespace, 1-255 characters (same rules as the backend)."""
    title = " ".join(raw.split())
    if not title:
        return None, "Tên không được để trống."
    if len(title) > MAX_TITLE_LENGTH:
        return None, f"Tên tối đa {MAX_TITLE_LENGTH} ký tự."
    return title, None


# ---------------------------------------------------------------------------- placeholder covers

def cover_hue(title: str) -> int:
    """Stable hue (0-359) for a title; mirrors apps/web/src/lib/cover.ts so both apps show the same colour."""
    value = 0
    for char in unicodedata.normalize("NFC", title):
        value = (value * 31 + ord(char)) % 3600
    return int(value / 10 + 0.5) % 360


def cover_color(title: str) -> str:
    """Hex colour of the generated cover (hsl(hue 55% 38%))."""
    import colorsys

    red, green, blue = colorsys.hls_to_rgb(cover_hue(title) / 360, 0.38, 0.55)
    return f"#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"


def cover_initials(title: str) -> str:
    """Up to two initials of the first words ("Đắc Nhân Tâm" -> "ĐN"); a note sign if there are none."""
    words = [w for w in title.split() if any(c.isalnum() for c in w)]
    letters = [next(c for c in w if c.isalnum()).upper() for w in words[:2]]
    return "".join(letters) or "♪"


# ---------------------------------------------------------------------------- accounts

def check_credentials(mode: str, username: str, password: str, confirm: str = "") -> str | None:
    """A message for the first problem found, else None. Mirrors the backend rules (and the web form)."""
    import re

    username = username.strip()
    if not username:
        return "Nhập tên đăng nhập."
    if not password:
        return "Nhập mật khẩu."
    if mode == "login":
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username):
        return "Tên đăng nhập dài 3–32 ký tự, chỉ gồm chữ cái không dấu, số, dấu chấm, gạch dưới hoặc gạch ngang."
    if len(password) < 8:
        return "Mật khẩu cần ít nhất 8 ký tự."
    if password != confirm:
        return "Mật khẩu nhập lại không khớp."
    return None


def avatar_letter(user: dict[str, Any]) -> str:
    """First letter of the display name (or username) for the avatar circle."""
    source = str(user.get("full_name") or user.get("username") or "").strip()
    return next((c.upper() for c in source if c.isalnum()), "?")
