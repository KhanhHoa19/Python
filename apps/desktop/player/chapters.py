"""Table-of-contents helpers (same rules as apps/web/src/lib/chapters.ts). No Tk."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any


def chapter_at(chapters: Sequence[dict[str, Any]], index: int) -> dict[str, Any] | None:
    """The chapter that contains sentence `index`; the nearest one if outside; None without chapters."""
    if not chapters:
        return None
    for chapter in chapters:
        if chapter["start_sentence_index"] <= index <= chapter["end_sentence_index"]:
            return chapter
    return chapters[0] if index < chapters[0]["start_sentence_index"] else chapters[-1]


def describe_chapter(chapter: dict[str, Any], format_number: Callable[[int], str]) -> str:
    """'12 câu · 340 từ' under a chapter title."""
    return f"{format_number(chapter['sentence_count'])} câu · {format_number(chapter['word_count'])} từ"
