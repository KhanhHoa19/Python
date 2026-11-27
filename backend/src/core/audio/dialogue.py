"""Multi-voice narration: tell the narrator's lines from the characters' lines.

A sentence is cut into segments. Dialogue is what sits inside quotation marks (“…”, "…", «…») or a line that starts
with a dialogue dash ("- Em đi đâu đấy? - Nam hỏi." speaks "Em đi đâu đấy?" and narrates "Nam hỏi.").
A quotation can run over several sentences, so the state "still inside a quotation" is carried from one sentence to
the next. The rules are text-only: no model, no stored labels, so they work on books that are already loaded.

Known limits (documented in docs/mockups/S03): a dash-dialogue turn that spans several sentences is only treated as
dialogue in its first sentence, and a dash that starts a bullet list reads as dialogue."""

from __future__ import annotations

from dataclasses import dataclass

OPENERS = {"“": "”", "«": "»"}
CLOSERS = {"”", "»"}
STRAIGHT = '"'
DASHES = ("-", "–", "—")
MAX_OPEN_SENTENCES = 12  # a quotation open this long is a stray mark (scan error), not a speech


@dataclass(frozen=True)
class Segment:
    text: str
    dialogue: bool


def _speakable(text: str) -> bool:
    return any(c.isalnum() for c in text)


def _merge(parts: list[Segment]) -> list[Segment]:
    """Drop empty pieces, glue marks-only pieces to a neighbour, join neighbours of the same kind."""
    merged: list[Segment] = []
    carry = ""
    for part in parts:
        text = part.text.strip()
        if not text:
            continue
        if not _speakable(text):  # "…" or "," between two quotes: the voice has nothing to say, keep it with its neighbour
            if merged:
                merged[-1] = Segment(f"{merged[-1].text}{text}", merged[-1].dialogue)  # "biệt" + "." stay together
            else:
                carry = f"{carry} {text}".strip()
            continue
        if carry:
            text, carry = f"{carry} {text}", ""
        if merged and merged[-1].dialogue == part.dialogue:
            merged[-1] = Segment(f"{merged[-1].text} {text}", part.dialogue)
        else:
            merged.append(Segment(text, part.dialogue))
    return merged


def _dash_line(text: str) -> list[Segment] | None:
    """"- Em đi đâu đấy? - Nam hỏi." -> speech, narration. None if the sentence does not start with a dialogue dash."""
    stripped = text.lstrip()
    if not stripped or stripped[0] not in DASHES:
        return None
    body = stripped[1:]
    if body and not body[0].isspace():  # "-5 độ" or "—và": not a dialogue dash
        return None
    pieces: list[Segment] = []
    dialogue, start = True, 0
    for index, char in enumerate(body):
        # A dash with spaces on both sides switches between the character and the narrator ("... ? - Nam hỏi.").
        if char in DASHES and 0 < index < len(body) - 1 and body[index - 1].isspace() and body[index + 1].isspace():
            pieces.append(Segment(body[start:index], dialogue))
            dialogue, start = not dialogue, index + 1
    pieces.append(Segment(body[start:], dialogue))
    return _merge(pieces)


def split_sentence(text: str, in_quote: bool = False) -> tuple[list[Segment], bool]:
    """Cut one sentence into segments. `in_quote` says whether a quotation is still open from the sentences before;
    the second value tells the same for the next sentence."""
    if not in_quote:
        dash = _dash_line(text)
        if dash is not None:
            return dash, False
    pieces: list[Segment] = []
    buffer: list[str] = []
    closing = ""  # the mark that closes the quotation we are in ("" for a straight quote)
    for char in text:
        opens = char in OPENERS and not in_quote
        closes = in_quote and (char == STRAIGHT if closing == STRAIGHT else char == closing or char in CLOSERS)
        straight_open = char == STRAIGHT and not in_quote
        if opens or straight_open or closes:
            pieces.append(Segment("".join(buffer), in_quote))
            buffer = []
            if closes:
                in_quote, closing = False, ""
            else:
                in_quote, closing = True, (STRAIGHT if straight_open else OPENERS[char])
        elif char in CLOSERS and not in_quote:
            continue  # a stray closing mark: nothing was open
        else:
            buffer.append(char)
    pieces.append(Segment("".join(buffer), in_quote))
    return _merge(pieces), in_quote


def quote_states(texts: list[str]) -> list[bool]:
    """For every sentence: is a quotation already open when it starts? (Carried across sentences.)"""
    states: list[bool] = []
    open_for = 0
    in_quote = False
    for text in texts:
        states.append(in_quote)
        _, in_quote = split_sentence(text, in_quote)
        open_for = open_for + 1 if in_quote else 0
        if open_for > MAX_OPEN_SENTENCES:  # never closed: stop treating the rest of the book as speech
            in_quote, open_for = False, 0
    return states


def has_dialogue(segments: list[Segment]) -> bool:
    return any(s.dialogue for s in segments)
