"""Text cleaning for extracted documents: Unicode/whitespace, wrapped lines, PDF page furniture.

Pure functions, no I/O. The reader calls them while loading a file and the sentence splitter
calls them again on its input (all of them are idempotent).
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

# Zero-width characters and the soft hyphen are invisible but break hashing and TTS.
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)
_UNICODE_SPACES = re.compile(r"[ \t\f\v   -   　]+")
_DECORATION = re.compile(r"^(?:[-_=*~#•]\s*){3,}$")  # "* * *", "-----", "=====", "###"
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")
_SPACE_BEFORE_PUNCT = re.compile(r"(?<=\S) +([.,;:!?])(?=\s|$)")  # "việc ." -> "việc."
_DOT_LEADER = re.compile(r"(?:\.\s*){6,}")  # "Chương 1 ........ 27" in tables of contents

# Characters that may wrap a sentence: closing quotes/brackets after the final punctuation,
# opening quotes/dashes before the first word.
_CLOSERS = "\"”’»)]'"
_OPENERS = " \"“‘«([\'-–—•*"
_TERMINAL = (".", "!", "?", "…")
# A line that starts a new item: bullet, dialogue dash, "1." / "1.2)" / "a)" style list marker.
_ITEM_START = re.compile(r"^(?:[-–—•*+]|\d+(?:\.\d+)*[.)]\s|[A-Za-zĐđ][.)]\s)")

def normalize_text(text: str) -> str:
    """NFC, no invisible characters, single spaces, no space before punctuation, no decorative lines/leaders."""
    text = unicodedata.normalize("NFC", text).translate(_INVISIBLE)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = (
        _SPACE_BEFORE_PUNCT.sub(r"\1", _UNICODE_SPACES.sub(" ", _DOT_LEADER.sub(" ", line))).strip()
        for line in text.split("\n")
    )
    kept = [line for line in lines if not _DECORATION.match(line)]
    return _EXCESS_BLANK_LINES.sub("\n\n", "\n".join(kept)).strip()


def _percentile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]


def _continues(previous: str, following: str, previous_width: int, typical_width: int | None) -> bool:
    """Is `following` the continuation of a line that was hard-wrapped after `previous`?"""
    if _ITEM_START.match(following):
        return False
    tail = previous.rstrip().rstrip(_CLOSERS)
    if tail.endswith((",", ";")):
        return True
    first = following.lstrip(_OPENERS)[:1]
    if tail.endswith(":"):
        return first.islower()
    if tail.endswith(_TERMINAL):
        return False
    if first.islower():
        return True
    # A capitalised continuation (proper noun) after a line that filled the page width.
    return bool(typical_width and previous_width >= 40 and previous_width >= 0.8 * typical_width)


def typical_line_width(text: str) -> int | None:
    """Width (90th percentile) of the document's lines; None if there are too few lines to tell."""
    widths = [len(line.strip()) for line in text.split("\n") if line.strip()]
    return _percentile(widths, 0.9) if len(widths) >= 5 else None


def join_wrapped_lines(text: str, typical_width: int | None = None) -> str:
    """Join lines that were hard-wrapped mid-sentence (typical for PDFs); keep headings and items.

    Blank lines are paragraph boundaries and are preserved. `typical_width` should come from the
    WHOLE document (see typical_line_width): measured on a short excerpt, such as a table of
    contents, it is too small and makes every full-looking line "wrapped".
    """
    lines = text.split("\n")
    typical = typical_width if typical_width is not None else typical_line_width(text)

    out: list[str] = []
    last_width = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append("")
            last_width = 0
            continue
        if out and out[-1] and _continues(out[-1], stripped, last_width, typical):
            out[-1] = f"{out[-1]} {stripped}"
        else:
            out.append(stripped)
        last_width = len(stripped)
    return "\n".join(out)


def _page_key(line: str) -> str:
    """Page-independent form of a line: digits masked so 'Trang 3' and 'Trang 4' match."""
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", line.lower())).strip()


def _edge_indexes(lines: list[str]) -> set[int]:
    """Indexes of the first two and last two non-empty lines of a page."""
    non_empty = [i for i, line in enumerate(lines) if line.strip()]
    return set(non_empty[:2]) | set(non_empty[-2:])


def remove_page_furniture(pages: list[str]) -> list[str]:
    """Drop running headers, footers and page numbers that repeat across pages.

    Digits are masked first, so "Trang 3" / "Trang 4" and bare page numbers all match. A line is
    furniture when it sits at the top or bottom of at least half of
    the pages (and at least three). Documents with fewer than three pages are returned unchanged.
    """
    if len(pages) < 3:
        return pages
    split_pages = [page.split("\n") for page in pages]
    counts: Counter[str] = Counter()
    for lines in split_pages:
        counts.update({_page_key(lines[i]) for i in _edge_indexes(lines)})
    threshold = max(3, math.ceil(len(pages) / 2))
    furniture = {key for key, seen in counts.items() if seen >= threshold}

    cleaned: list[str] = []
    for lines in split_pages:
        edges = _edge_indexes(lines)
        kept = [line for i, line in enumerate(lines) if not (i in edges and _page_key(line) in furniture)]
        cleaned.append("\n".join(kept).strip("\n"))
    return cleaned


def merge_pages(pages: list[str]) -> str:
    """Concatenate pages with a single newline so a sentence can continue across a page break."""
    return "\n".join(page.strip("\n") for page in pages if page.strip())
