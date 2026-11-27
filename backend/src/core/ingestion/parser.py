"""Rule-based sentence splitter (Vietnamese + English) with clause/length sub-segmentation."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any

from src.core.ingestion.cleaner import join_wrapped_lines, normalize_text, typical_line_width

DEFAULT_MAX_CLAUSE_WORDS = 35
DEFAULT_MAX_CHARS = 300

# A period after one of these never ends a sentence: a name or number follows ("TP. Hồ Chí Minh",
# "PGS.TS. Nguyễn Văn A", "Dr. Watson"). Lowercase, without the final dot; dotted chains such as
# "pgs.ts" are matched part by part.
TITLE_ABBREVIATIONS = frozenset({
    # Vietnamese titles, places, organisations
    "tp", "tt", "ts", "ths", "pgs", "gs", "bs", "ks", "cn", "ds", "đh", "cđ", "tw", "nxb",
    "sđt", "đt",
    # English
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "gen", "col", "capt", "lt", "st", "ave", "rd", "blvd",
    "e.g", "i.e", "vs", "etc", "approx", "dept", "est", "govt", "inc", "ltd", "corp",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
})
# These may legitimately end a sentence ("... rau, củ, v.v. Sau đó ..."), so the period only
# continues the sentence when a lowercase word or a number follows ("v.v. và", "tr. 25").
WEAK_ABBREVIATIONS = frozenset({"v.v", "vv", "vd", "v.d", "tr"})

# Punctuation run, optional closing quotes/brackets, then whitespace: a candidate sentence end.
_BOUNDARY = re.compile(r"([.!?…]+)([\"”’»)\]']*)(\s+)")
_OPENERS = " \"“‘«([\'-–—•*"
# "1." "1.2." "A." "II." "a." at the very start of a unit are list/section markers, not sentences.
_LIST_MARKER = re.compile(r"^(?:\d+(?:\.\d+)*|[A-Za-zĐđ]|[IVXLCDM]+)$")
# "quốc.Nhưng": two lowercase letters, sentence punctuation, then a capitalised word with no space.
_MISSING_SPACE = re.compile(r"([^\W\d_]{2})([.!?])([^\W\d_])(?=[^\W\d_])")
_CLAUSE_BREAK = re.compile(r"(?<=[,;:—–])\s+|(?<=--)\s+")

_ORDINALS = (
    "nhất|nhì|hai|ba|tư|bốn|năm|sáu|bảy|tám|chín|mười|one|two|three|four|five|six|seven|eight|nine|ten"
)
# "Phần thứ nhất", "Part 2", "Phần II": a part groups chapters (each part may restart at "Chương 1").
_PART_HEADING = re.compile(rf"^(?:phần|part)\s+(?:thứ\s+)?(?:[\dIVXLCDM]+|{_ORDINALS})\b", re.IGNORECASE)
# A line of a table of contents ends with its page number: "Chương 7 Giải đáp 198", "ABBEY GRANGE 3".
_TOC_ENTRY = re.compile(r"^(?P<title>\S.{2,100}?\S)\s+(?P<page>\d{1,4})$")
_TOC_MARKER = re.compile(r"^(?:mục lục|table of contents|contents)$", re.IGNORECASE)
_ROMAN = re.compile(r"^(?=[IVXLCDM])M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")
_NUMBERED = re.compile(r"^(?P<kw>chapter|section|part|chương|phần|bài|mục)\s+(?P<num>[IVXLCDM]+)\b(?P<rest>.*)$", re.IGNORECASE)
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
SUBTITLE_MAX_WORDS = 10
TITLE_SEPARATOR = " · "


def _roman_to_int(numeral: str) -> int:
    total = 0
    for index, char in enumerate(numeral):
        value = _ROMAN_VALUES[char]
        total += -value if index + 1 < len(numeral) and _ROMAN_VALUES[numeral[index + 1]] > value else value
    return total


def tidy_heading(heading: str) -> str:
    """"Chương I" -> "Chương 1": scans and OCR mix Roman and Arabic numerals, which makes chapters look repeated."""
    match = _NUMBERED.match(heading)
    if not match or not _ROMAN.match(match["num"].upper()) or match["num"] != match["num"].upper():
        return heading
    value = _roman_to_int(match["num"])
    return f"{match['kw']} {value}{match['rest']}" if value <= 100 else heading


def is_toc_entry(stripped: str) -> bool:
    """A table-of-contents line (a title followed by a page number), not a heading of the text itself."""
    match = _TOC_ENTRY.match(stripped)
    return match is not None and len(stripped.split()) >= 4 and not match["title"].isdigit()


def toc_titles(lines: list[str]) -> set[str]:
    """Titles listed in the document's own table of contents ("HỘI TÓC HUNG 73"): a later line equal to one starts a chapter."""
    found: set[str] = set()
    for position, line in enumerate(lines):
        if not _TOC_MARKER.match(line.strip()):
            continue
        for entry in lines[position + 1:position + 80]:
            stripped = entry.strip()
            match = _TOC_ENTRY.match(stripped)
            if match and not _CHAPTER_HEADING.match(stripped) and not _PART_HEADING.match(stripped):
                found.add(normalize_heading(match["title"]))
            elif len(stripped.split()) > 15:
                break  # the first real paragraph: the table of contents is over
    return {t for t in found if t}


def _is_subtitle(stripped: str) -> bool:
    """A short ALL-CAPS line right after a bare heading ("Chương 1" / "TIN BÁO") is that chapter's name."""
    words = stripped.split()
    return (bool(words) and len(words) <= SUBTITLE_MAX_WORDS and stripped.isupper()
            and not stripped.endswith((".", "!", "?", "…")) and not stripped.isdigit()
            and not _CHAPTER_HEADING.match(stripped) and not _PART_HEADING.match(stripped))


def _title(*labels: str | None) -> str:
    return TITLE_SEPARATOR.join(label for label in labels if label)


_CHAPTER_HEADING = re.compile(
    r"^(?:#{1,3}\s+(.+)|(?:chapter|section|part|chương|phần|bài|mục)\s+[\dIVXLCDM]+\b.*)",
    re.IGNORECASE,
)


def _insert_missing_spaces(text: str) -> str:
    """Add the space a typist forgot after a sentence end, leaving web addresses and emails alone."""

    def fix(match: re.Match[str]) -> str:
        before, mark, initial = match.group(1), match.group(2), match.group(3)
        following = match.string[match.end()]
        if not (before.islower() and initial.isupper() and following.islower()):
            return match.group(0)
        context = match.string[max(0, match.start() - 30): match.end() + 30].lower()
        if any(marker in context for marker in ("www", "http", "@", "/")):
            return match.group(0)
        return f"{before}{mark} {initial}"

    return _MISSING_SPACE.sub(fix, text)


def _is_abbreviation(token: str, abbreviations: frozenset[str]) -> bool:
    word = token.strip(_OPENERS).lower()
    if word in abbreviations:
        return True
    parts = [part for part in word.split(".") if part]
    return len(parts) > 1 and all(part in abbreviations for part in parts)


def _starts_sentence(following: str) -> bool:
    """True if the text after a period reads like a new sentence (not a lowercase continuation)."""
    rest = following.lstrip(_OPENERS)
    return not rest or not rest[0].islower()


def _is_boundary(before: str, punct: str, following: str) -> bool:
    """Decide whether the punctuation run after `before` really ends a sentence."""
    if "!" in punct or "?" in punct:
        return True
    if "…" in punct or len(punct) > 1:  # ellipsis: only a sentence end if a new sentence follows
        return _starts_sentence(following)

    tokens = before.split()
    token = tokens[-1] if tokens else ""
    if _is_abbreviation(token, TITLE_ABBREVIATIONS):
        return False
    if _is_abbreviation(token, WEAK_ABBREVIATIONS):
        rest = following.lstrip(_OPENERS)
        return bool(rest) and rest[0].isupper()
    if len(tokens) == 1 and _LIST_MARKER.match(token):
        return False
    return _starts_sentence(following)


def _split_sentences(unit: str) -> list[str]:
    """Split one logical line into sentences."""
    sentences: list[str] = []
    start = 0
    for match in _BOUNDARY.finditer(unit):
        if _is_boundary(unit[start:match.start(1)], match.group(1), unit[match.end():]):
            sentences.append(unit[start:match.end(2)].strip())
            start = match.end()
    tail = unit[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def _too_long(text: str, max_words: int, max_chars: int | None) -> bool:
    return len(text.split()) > max_words or bool(max_chars and len(text) > max_chars)


def _hard_split(text: str, max_words: int, max_chars: int | None) -> list[str]:
    """Last resort: cut at word boundaries so every piece fits the limits."""
    pieces: list[str] = []
    current: list[str] = []
    for word in text.split():
        trial = [*current, word]
        if current and _too_long(" ".join(trial), max_words, max_chars):
            pieces.append(" ".join(current))
            current = [word]
        else:
            current = trial
    if current:
        pieces.append(" ".join(current))
    return pieces


def _split_long_clause(sentence: str, max_words: int = DEFAULT_MAX_CLAUSE_WORDS,
                       max_chars: int | None = DEFAULT_MAX_CHARS) -> list[str]:
    """Break an over-long sentence at clause punctuation (, ; : — –), then by words if needed.

    Breaks only occur where whitespace follows the punctuation, so decimals such as "3,5" are safe.
    """
    if not _too_long(sentence, max_words, max_chars):
        return [sentence]

    chunks: list[str] = []
    current = ""
    for clause in _CLAUSE_BREAK.split(sentence):
        candidate = f"{current} {clause}" if current else clause
        if _too_long(candidate, max_words, max_chars):
            if current:
                chunks.append(current)
            current = clause
        else:
            current = candidate
    if current:
        chunks.append(current)

    result: list[str] = []
    for chunk in chunks:
        result.extend(_hard_split(chunk, max_words, max_chars) if _too_long(chunk, max_words, max_chars) else [chunk])
    return result


def tokenize_sentences(text: str, max_clause_words: int = DEFAULT_MAX_CLAUSE_WORDS,
                       max_chars: int | None = DEFAULT_MAX_CHARS,
                       typical_width: int | None = None) -> list[str]:
    """Split raw text into clean, ordered sentences, none longer than the given limits.

    Pipeline: normalise Unicode/whitespace -> join hard-wrapped lines -> split each logical line
    into sentences (Vietnamese/English abbreviations, decimals, ellipses, quotes, list markers)
    -> cut over-long sentences at clause punctuation, then by words.
    """
    if not text or not text.strip():
        return []

    results: list[str] = []
    for line in join_wrapped_lines(_insert_missing_spaces(normalize_text(text)), typical_width).split("\n"):
        unit = line.strip()
        if not unit:
            continue
        for sentence in _split_sentences(unit):
            results.extend(c.strip() for c in _split_long_clause(sentence, max_clause_words, max_chars) if c.strip())
    return results


PREFACE_TITLE = "Mở đầu"  # title of the text that comes before the first heading
WHOLE_DOCUMENT_TITLE = "Toàn bộ tài liệu"  # title of a document in which no heading was found
_HEADING_EDGE = " \t.:;,·-–—"


def normalize_heading(text: str) -> str:
    """Lower-case, single-spaced, no edge punctuation: lets a heading found in the file's own outline
    (PDF bookmarks, Word Heading 1) be matched against a line of the extracted text."""
    return " ".join(unicodedata.normalize("NFC", text).lower().split()).strip(_HEADING_EDGE)


def _is_heading(stripped: str, hints: frozenset[str] = frozenset()) -> bool:
    if is_toc_entry(stripped):
        return False
    if hints and len(stripped.split()) <= 20 and normalize_heading(stripped) in hints:
        return True
    if not (_CHAPTER_HEADING.match(stripped) or _PART_HEADING.match(stripped)):
        return False
    if stripped.startswith("#"):
        return True
    words = stripped.split()
    ends_like_a_sentence = stripped.rstrip(_OPENERS + "\"”’»)").endswith((".", "!", "?", "…"))
    return len(words) <= 15 and (not ends_like_a_sentence or len(words) <= 4)


def split_into_chapters_and_sentences(
    document_text: str,
    max_clause_words: int = DEFAULT_MAX_CLAUSE_WORDS,
    max_chars: int | None = DEFAULT_MAX_CHARS,
    heading_hints: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Detect chapters (Markdown headings, 'Chapter N', 'Chương N', 'Phần N', 'Bài N', 'Mục N')
    and split each into sentences. `heading_hints` are titles from the file's own outline; a line
    that equals one of them (ignoring case and edge punctuation) also starts a chapter."""
    document_text = normalize_text(document_text)
    all_lines = document_text.splitlines()
    hints = frozenset(h for h in (normalize_heading(t) for t in heading_hints) if h) | toc_titles(all_lines)
    chapters: list[dict[str, Any]] = []
    current_title = PREFACE_TITLE
    current_lines: list[str] = []
    work: str | None = None  # a story/work title that has no text of its own, e.g. the name above "Phần thứ nhất"
    part: str | None = None  # "Phần thứ nhất": the following chapters belong to it
    subtitle_target: str | None = None  # "chapter" | "part": what an ALL-CAPS line right after the heading names
    bare_heading = ""

    typical_width = typical_line_width(document_text)  # measured on the whole document, not a chapter

    def finish_chapter() -> None:
        sentences = tokenize_sentences("\n".join(current_lines), max_clause_words, max_chars, typical_width)
        if sentences:
            chapters.append({"title": current_title, "sentences": sentences})

    def has_text() -> bool:
        return any(line.strip() for line in current_lines)

    def start(title: str) -> None:
        nonlocal current_title, current_lines
        finish_chapter()
        current_lines = []
        current_title = title

    for line in all_lines:
        stripped = line.strip()
        if subtitle_target and stripped:
            target, subtitle_target = subtitle_target, None
            if _is_subtitle(stripped) and not (hints and normalize_heading(stripped) in hints):
                if target == "chapter":
                    current_title = _title(work, part, bare_heading, stripped)
                else:
                    current_title = _title(work, part, stripped)
                current_lines.append(line)  # the name is still read aloud as the first sentence of the chapter
                continue
        if not _is_heading(stripped, hints):
            current_lines.append(line)
            continue
        text = re.sub(r"^#+\s*", "", stripped).strip() if stripped.startswith("#") else stripped
        text = tidy_heading(text)
        if _PART_HEADING.match(text):
            if not has_text():  # the text before this part was only a title: it names the whole work
                work = current_title if current_title not in (PREFACE_TITLE, work) and hints else work
            part = text
            start(_title(work, part))
            subtitle_target, bare_heading = ("part" if len(text.split()) <= 4 else None), text
        elif _CHAPTER_HEADING.match(stripped) or stripped.startswith("#"):
            start(_title(work, part, text))
            subtitle_target, bare_heading = ("chapter" if len(text.split()) <= 4 else None), text
        else:  # a title taken from the file's own outline or table of contents
            if not has_text() and current_title != PREFACE_TITLE and normalize_heading(current_title) in hints:
                work = current_title  # two titles in a row: the first one is the work, the second a chapter of it
            elif has_text() or current_title == PREFACE_TITLE:
                work = None
            part = None
            start(_title(work, text) if work else text)
            subtitle_target = None
    finish_chapter()
    return chapters
