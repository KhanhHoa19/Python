"""Library data that is not tied to one request: default categories and the start-up backfill of older books."""

from __future__ import annotations

import logging

from sqlalchemy import Engine, text

from src.core.ingestion.covers import generate_default_cover, hue_for, save_cover
from src.core.text_search import normalize_search

logger = logging.getLogger(__name__)

# (name, slug, icon (a lucide icon name), colour, hue of the generated cover)
DEFAULT_CATEGORIES = [
    ("Tiểu thuyết", "tieu-thuyet", "book-open", "#c2566b"),
    ("Trinh thám", "trinh-tham", "search", "#5b6b8c"),
    ("Khoa học", "khoa-hoc", "flask-conical", "#2f8f9d"),
    ("Lịch sử", "lich-su", "landmark", "#a0722d"),
    ("Kỹ năng sống", "ky-nang-song", "sprout", "#3f9b6a"),
    ("Tâm lý", "tam-ly", "brain", "#b5649a"),
    ("Triết học", "triet-hoc", "lightbulb", "#8a7a3a"),
    ("Công nghệ", "cong-nghe", "cpu", "#3b82c4"),
    ("Kinh tế", "kinh-te", "trending-up", "#d08a1f"),
    ("Tình cảm", "tinh-cam", "heart", "#d1566f"),
    ("Kinh dị", "kinh-di", "ghost", "#6b4a8c"),
    ("Phiêu lưu", "phieu-luu", "compass", "#c27a3a"),
    ("Thiếu nhi", "thieu-nhi", "baby", "#4aa3c9"),
    ("Truyện ngắn", "truyen-ngan", "feather", "#8b5cc4"),
    ("Khác", "khac", "layers", "#7a7468"),
]
CATEGORIES_FLAG = "seeded_categories_v2"


def hue_of_color(color: str) -> int:
    """Hue (0-359) of a #rrggbb colour, used to tint the generated cover of a categorised book."""
    import colorsys

    red, green, blue = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return round(colorsys.rgb_to_hls(red, green, blue)[0] * 360) % 360


def ensure_default_categories(engine: Engine) -> None:
    """The 15 topic tags. Runs once: a fresh database gets all of them, an older one gets the missing ones.

    After that the table belongs to the admins (they may rename, add or delete tags), so a deleted tag is not brought back."""
    with engine.begin() as conn:
        if conn.execute(text("SELECT 1 FROM app_settings WHERE setting_key = :k"), {"k": CATEGORIES_FLAG}).fetchone():
            return
        have = {r[0] for r in conn.execute(text("SELECT slug FROM categories"))}
        order = int(conn.execute(text("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM categories")).scalar() or 0)
        for name, slug, icon, color in DEFAULT_CATEGORIES:
            if slug in have:
                continue
            conn.execute(
                text("INSERT INTO categories (name, slug, icon, color, sort_order) VALUES (:n, :s, :i, :c, :o)"),
                {"n": name, "s": slug, "i": icon, "c": color, "o": order},
            )
            order += 1
        conn.execute(text("INSERT INTO app_settings (setting_key, setting_value) VALUES (:k, '1')"), {"k": CATEGORIES_FLAG})


def backfill_book_extras(engine: Engine) -> None:
    """Books added before categories and covers existed get search text and a generated cover (idempotent)."""
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, title, author FROM books WHERE search_text IS NULL")).fetchall()
        for book_id, title, author in rows:
            conn.execute(
                text("UPDATE books SET search_text = :s WHERE id = :id"),
                {"s": normalize_search(f"{title} {author or ''}")[:600], "id": book_id},
            )
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, title, author FROM books WHERE cover_path IS NULL")).fetchall()
        for book_id, title, author in rows:
            name = save_cover(generate_default_cover(title, author or "", hue_for(title)))
            conn.execute(text("UPDATE books SET cover_path = :c WHERE id = :id"), {"c": name, "id": book_id})
    if rows:
        logger.info("Generated covers for %d book(s)", len(rows))
