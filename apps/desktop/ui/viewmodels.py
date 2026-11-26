"""Pure helpers for the UI (no Tk imports) so they can be unit-tested."""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Any

SORT_OPTIONS = ("Đọc gần đây", "Tên A→Z", "Ngày thêm", "Tiến độ")


def normalize_text(value: str) -> str:
    """Lowercase and strip Vietnamese diacritics so search ignores case and accents."""
    decomposed = unicodedata.normalize("NFD", value.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
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
    total = int(round(minutes))
    hours, mins = divmod(total, 60)
    return f"{hours} giờ {mins:02d}" if hours else f"{mins} phút"


def format_number(value: float | int) -> str:
    """Thousands separated by dots: 96200 -> '96.200'."""
    return f"{int(round(value)):,}".replace(",", ".")


def progress_fraction(bookmark: dict[str, Any] | None) -> float:
    if not bookmark:
        return 0.0
    return min(max(float(bookmark.get("completion_percentage", 0.0)) / 100.0, 0.0), 1.0)


def filter_and_sort_books(books: list[dict[str, Any]], query: str, sort_by: str) -> list[dict[str, Any]]:
    """`books` items are API book dicts with an optional 'bookmark' dict attached by the UI."""
    needle = normalize_text(query.strip())
    items = [b for b in books if needle in normalize_text(f"{b.get('title', '')} {b.get('author', '')}")]

    def last_read(book: dict[str, Any]) -> float:
        parsed = parse_iso((book.get("bookmark") or {}).get("last_read_at"))
        return parsed.timestamp() if parsed else 0.0

    if sort_by == "Tên A→Z":
        items.sort(key=lambda b: normalize_text(b.get("title", "")))
    elif sort_by == "Ngày thêm":
        items.sort(key=lambda b: parse_iso(b.get("created_at")) or datetime.min, reverse=True)
    elif sort_by == "Tiến độ":
        items.sort(key=lambda b: progress_fraction(b.get("bookmark")), reverse=True)
    else:
        items.sort(key=last_read, reverse=True)
    return items


def most_recent_unfinished(books: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The book to resume on startup: read before (progress > 0), not finished, latest first."""
    candidates = [
        b for b in books
        if 0.0 < progress_fraction(b.get("bookmark")) < 1.0 and (b.get("bookmark") or {}).get("last_read_at")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda b: parse_iso(b["bookmark"]["last_read_at"]) or datetime.min)


def describe_voice(voice: dict[str, Any]) -> str:
    """'Hoài My · Nữ · kể chuyện' style label for lists and dropdowns."""
    gender = {"female": "Nữ", "male": "Nam"}.get(str(voice.get("gender") or "").lower(), "")
    parts = [voice.get("display_name", voice.get("voice_id", "")), gender, voice.get("style") or ""]
    if voice.get("is_custom"):
        parts.append("Giọng của tôi")
    return " · ".join(p for p in parts if p)


def usage_ratio(used: int, limit: int) -> float:
    """0..1 share of the daily character limit; 0 when unlimited."""
    return min(used / limit, 1.0) if limit > 0 else 0.0
