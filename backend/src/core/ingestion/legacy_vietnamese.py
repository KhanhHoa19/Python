"""Decode Vietnamese text produced by legacy "VietWare" (.Vn*) fonts, e.g. VnTime, VnNCentury2.

Old Word/PDF files used 8-bit fonts whose glyphs sit on Latin-1 code points, so the extracted
text is garbage such as "CUÖÅC PHÛU LÛU" (= "CUỘC PHƯU LƯU"). The text layer carries no hint of
the real letters, but the mapping is fixed and was verified against a 258-page book:

* Letters with a hat, horn, breve or stroke are ONE character:  à=đ  ê=â  ï=ê  ö=ô  ú=ơ  û=ư  ù=ă
* í ì ỉ ĩ ị are ONE character (codes F1-F5, in tone order):    ñ=í  ò=ì  ó=ỉ  ô=ĩ  õ=ị
* Tone marks are a SEPARATE character after the vowel, and the character depends on the vowel:
    plain a e i o u y, and ơ ư :  á=sắc  â=huyền  ã=hỏi  ä=ngã  å=nặng
    â ê ô (circumflex)         :  ë=sắc  ì=huyền  í=hỏi  î=ngã  å=nặng
    ă (breve)                  :  æ=sắc  ç=huyền  è=hỏi  é=ngã  å=nặng
  Upper case uses the upper-case Latin-1 counterpart (À=Đ, Ö=Ô, Å=nặng, ...).

Detection is statistical (see `looks_like_vietware`) so it works without knowing the font name.
"""

from __future__ import annotations

import re
import unicodedata

_SINGLE_LETTERS = {
    "à": "đ", "ù": "ă", "ê": "â", "ï": "ê", "ö": "ô", "ú": "ơ", "û": "ư",
    "ñ": "í", "ò": "ì", "ó": "ỉ", "ô": "ĩ", "õ": "ị",
}
_COMBINING = {
    "acute": "́", "grave": "̀", "hook": "̉", "tilde": "̃", "dot": "̣",
}
_TONES = {
    "á": "acute", "ë": "acute", "æ": "acute",
    "â": "grave", "ì": "grave", "ç": "grave",
    "ã": "hook", "í": "hook", "è": "hook",
    "ä": "tilde", "î": "tilde", "é": "tilde",
    "å": "dot",
}

# Upper-case counterparts share the lower-case meaning (Latin-1 case pairs).
LETTER_MAP: dict[str, str] = {}
for _src, _dst in _SINGLE_LETTERS.items():
    LETTER_MAP[_src] = _dst
    LETTER_MAP[_src.upper()] = _dst.upper()
TONE_MAP: dict[str, str] = {}
for _src, _tone in _TONES.items():
    TONE_MAP[_src] = _COMBINING[_tone]
    TONE_MAP[_src.upper()] = _COMBINING[_tone]

# Vowels that can carry a tone mark (after letter mapping).
_VOWELS = set("aeiouyâêôơưăAEIOUYÂÊÔƠƯĂ")
# Characters that real Vietnamese Unicode text almost never contains but legacy text is full of.
_TELLTALE = "åöûïë"
_VIETNAMESE_BLOCK = range(0x1EA0, 0x1EFA)  # ạ ả ấ ầ ... ỹ


def looks_like_vietware(text: str) -> bool:
    """True if `text` is Vietnamese stored in a VietWare (.Vn*) font and not yet real Unicode.

    Legacy text uses å ö û ï ë constantly (about 2% each) and never contains precomposed Vietnamese
    letters such as ạ ấ ỉ; genuine Unicode Vietnamese is the opposite. German/French/Swedish text
    has some of those letters but not four of the five at once.
    """
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 200:
        return False
    total = len(letters)
    if sum(1 for c in letters if ord(c) in _VIETNAMESE_BLOCK) / total >= 0.002:
        return False
    present = sum(1 for ch in _TELLTALE if sum(1 for c in letters if c.lower() == ch) / total >= 0.003)
    return present >= 4


def _attach_tone(out: list[str], mark: str) -> bool:
    """Put a tone mark on the preceding vowel. PDF extractors often insert a space between a letter
    and its separately-drawn tone glyph ("hiê åu"), and a tone never starts a word, so one space
    in between is dropped. Returns False (nothing changed) if there is no vowel to carry it."""
    index = len(out) - 1
    if index >= 1 and out[index] == " " and out[index - 1] in _VOWELS:
        out.pop()
        index -= 1
    if index < 0 or out[index] not in _VOWELS:
        return False
    out[index] = unicodedata.normalize("NFC", out[index] + mark)
    return True


def decode_vietware(text: str) -> str:
    """Convert VietWare-encoded text to normal Unicode (NFC). Other characters are left unchanged."""
    out: list[str] = []
    for char in text:
        if char in LETTER_MAP:
            out.append(LETTER_MAP[char])
        elif char in TONE_MAP and _attach_tone(out, TONE_MAP[char]):
            continue
        else:
            out.append(char)
    return unicodedata.normalize("NFC", "".join(out))


# --------------------------------------------------------------------------- split-syllable repair
# These PDFs also make the extractor insert a space INSIDE a syllable ("t ôi", "ng ười", "nê n",
# "khôn g"). A lone consonant is never a Vietnamese word, so it can be glued back to a neighbour.

_WORD = re.compile(r"[^\W\d_]+")
_SYLLABLE = re.compile(
    r"^(?:ngh|ng|nh|ph|th|tr|ch|gh|gi|kh|qu|[bcdđghklmnpqrstvx]|)"
    r"(?:[aeiouy][(^+]?){1,3}"
    r"(ch|ng|nh|[cmnpt]|)$"
)
_CONSONANT_ONLY = frozenset(
    "b c ch d đ g gh h k kh l m n ng ngh nh p ph q qu r s t th tr v x".split()
)
_TONE_MARKS = {"\u0300": "f", "\u0301": "s", "\u0303": "x", "\u0309": "r", "\u0323": "j"}
_SHAPE_MARKS = {"\u0306": "(", "\u0302": "^", "\u031b": "+"}


def _is_syllable(word: str) -> bool:
    """Does `word` have the shape of a Vietnamese syllable (onset + vowels + coda, tone rules)?"""
    tone = None
    shape: list[str] = []
    for char in unicodedata.normalize("NFD", word.lower()):
        if char in _TONE_MARKS:
            tone = _TONE_MARKS[char]
        elif char in _SHAPE_MARKS:
            shape.append(_SHAPE_MARKS[char])
        elif char.isalpha():
            shape.append(char)
        else:
            return False
    match = _SYLLABLE.match("".join(shape))
    if not match:
        return False
    # Syllables closed by c, ch, p or t can only carry the sắc or nặng tone.
    return not (match.group(1) in ("c", "ch", "p", "t") and tone not in (None, "s", "j"))


def _repair_line(line: str) -> str:
    matches = list(_WORD.finditer(line))
    if len(matches) < 2:
        return line

    def single_space(i: int) -> bool:  # words i and i+1 are separated by exactly one space
        return i + 1 < len(matches) and line[matches[i].end():matches[i + 1].start()] == " "

    spans: list[tuple[str, int, int]] = []  # (text, start, end) after merging
    i = 0
    while i < len(matches):
        text, start, end = matches[i].group(), matches[i].start(), matches[i].end()
        while single_space(i):
            nxt = matches[i + 1].group()
            if text.lower() in _CONSONANT_ONLY and _is_syllable(text + nxt):
                merge = True  # "t" + "ôi": the lone consonant is the onset of the next word
            elif nxt.lower() in _CONSONANT_ONLY and _is_syllable(text + nxt):
                # "nê" + "n" is a coda, unless the consonant is really the onset of the word after it
                after = matches[i + 2].group() if single_space(i + 1) else ""
                merge = not (after and _is_syllable(nxt + after))
            else:
                merge = False
            if not merge:
                break
            text, end, i = text + nxt, matches[i + 1].end(), i + 1
        spans.append((text, start, end))
        i += 1

    pieces: list[str] = [line[: spans[0][1]]]
    for index, (text, _, end) in enumerate(spans):
        pieces.append(text)
        pieces.append(line[end: spans[index + 1][1]] if index + 1 < len(spans) else line[end:])
    return "".join(pieces)


def repair_split_syllables(text: str) -> str:
    """Glue back syllables the PDF extractor split with a stray space ("t ôi" -> "tôi")."""
    return "\n".join(_repair_line(line) for line in text.split("\n"))


def decode_legacy_text(text: str) -> str:
    """Full pipeline for VietWare text: character decoding, then split-syllable repair."""
    return repair_split_syllables(decode_vietware(text))
