"""Text as the voice should hear it.

Speech engines treat an ALL-CAPS word as an acronym and spell it letter by letter or mangle it
("THUNG LŨNG KHỦNG KHIẾP" in a chapter title, "TIN BÁO", a shouted line). Before synthesis such words are
written in normal case. Short caps words (VN, USA, TV, NASA) stay: those really are acronyms."""

from __future__ import annotations

import re

ACRONYM_MAX_LETTERS = 4  # a caps word this short, in a sentence with lowercase words, is read as an acronym
_ROMAN = re.compile(r"^(?=[IVXLCDM])M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")
_WORD = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", re.UNICODE)


def _letters(text: str) -> str:
    return "".join(c for c in text if c.isalpha())


def _is_shouted(letters: str) -> bool:
    return len(letters) >= 2 and letters.isupper()


def prepare_speech_text(text: str) -> str:
    """`text` with ALL-CAPS words turned into normal case; everything else is returned unchanged."""
    letters = _letters(text)
    if len(letters) < 2 or not any(c.isupper() for c in letters):
        return text
    if letters.isupper() and len(letters) > ACRONYM_MAX_LETTERS:
        # The whole sentence is capitals (a title, a shout): "TIN BÁO" -> "Tin báo".
        lowered = text.lower()
        for index, char in enumerate(lowered):
            if char.isalpha():
                return lowered[:index] + char.upper() + lowered[index + 1:]
        return lowered

    words = list(_WORD.finditer(text))
    shouted = [_is_shouted(_letters(m.group(0))) and not _ROMAN.match(_letters(m.group(0))) for m in words]
    lower = [False] * len(words)
    for index, match in enumerate(words):
        if not shouted[index]:
            continue
        long_word = len(_letters(match.group(0))) > ACRONYM_MAX_LETTERS
        # Two capital words side by side ("ĐỨNG LẠI NGAY") are a shout, however short; a lone short one is an acronym.
        neighbour = (index > 0 and shouted[index - 1] and not text[words[index - 1].end():match.start()].strip(" ")) or (
            index + 1 < len(words) and shouted[index + 1] and not text[match.end():words[index + 1].start()].strip(" "))
        lower[index] = long_word or neighbour
    out, last = [], 0
    for index, match in enumerate(words):
        out.append(text[last:match.start()])
        out.append(match.group(0).lower() if lower[index] else match.group(0))
        last = match.end()
    out.append(text[last:])
    return "".join(out)
