"""Accent-insensitive search text: "Đắc Nhân Tâm" is found by typing "dac nhan tam"."""

from __future__ import annotations

import unicodedata


def normalize_search(text: str) -> str:
    """Lower-case, no accents (đ -> d), single spaces. Stored in books.search_text and applied to the query."""
    decomposed = unicodedata.normalize("NFKD", text.replace("đ", "d").replace("Đ", "D"))
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(plain.lower().split())


def search_tokens(query: str) -> list[str]:
    """The words a book must ALL contain (in any order) to match `query`."""
    return normalize_search(query).split()
