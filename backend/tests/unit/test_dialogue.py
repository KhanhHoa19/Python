"""Telling the narrator's lines from the characters' lines."""

from __future__ import annotations

import pytest

from src.core.audio.dialogue import Segment, has_dialogue, quote_states, split_sentence


def parts(text: str, in_quote: bool = False) -> list[tuple[str, bool]]:
    return [(s.text, s.dialogue) for s in split_sentence(text, in_quote)[0]]


@pytest.mark.parametrize(("text", "expected"), [
    ('Anh ta nói: "Đừng đi!" rồi quay đi.', [("Anh ta nói:", False), ("Đừng đi!", True), ("rồi quay đi.", False)]),
    ("Cô thì thầm: “Tôi sợ… thật sự sợ.” Rồi im.", [("Cô thì thầm:", False), ("Tôi sợ… thật sự sợ.", True), ("Rồi im.", False)]),
    ("«Chào» và “tạm biệt”.", [("Chào", True), ("và", False), ("tạm biệt.", True)]),
    ("“A,” anh nói, “B.”", [("A,", True), ("anh nói,", False), ("B.", True)]),
    ("Trời mưa to suốt đêm.", [("Trời mưa to suốt đêm.", False)]),
])
def test_quotation_marks(text: str, expected: list[tuple[str, bool]]) -> None:
    assert parts(text) == expected


@pytest.mark.parametrize(("text", "expected"), [
    ("- Em đi đâu đấy? - Nam hỏi.", [("Em đi đâu đấy?", True), ("Nam hỏi.", False)]),
    ("— Không.", [("Không.", True)]),
    ("- Tôi biết, - cô đáp, - nhưng không nói.", [("Tôi biết,", True), ("cô đáp,", False), ("nhưng không nói.", True)]),
])
def test_dialogue_dash(text: str, expected: list[tuple[str, bool]]) -> None:
    assert parts(text) == expected


@pytest.mark.parametrize("text", ["Nhiệt độ -5 độ C.", "Từ 1990 - 2000 là giai đoạn đầu.", "—và rồi", "-5 độ"])
def test_a_hyphen_or_minus_is_not_dialogue(text: str) -> None:
    assert not has_dialogue(split_sentence(text)[0])


def test_a_plain_sentence_is_left_exactly_as_it_was() -> None:
    """Narration keeps its original text, so audio cached before this feature still matches."""
    text = "Ông Wilson đến gặp Holmes vào một chiều thu."
    assert split_sentence(text)[0] == [Segment(text, False)]


def test_a_quotation_can_run_over_several_sentences() -> None:
    texts = ["Anh nói: “Chuyện này dài lắm", "ban đầu chúng tôi không biết", "cuối cùng mọi người hiểu.” Rồi anh đi."]
    states = quote_states(texts)
    assert states == [False, True, True]
    assert parts(texts[1], states[1]) == [("ban đầu chúng tôi không biết", True)]
    assert parts(texts[2], states[2]) == [("cuối cùng mọi người hiểu.", True), ("Rồi anh đi.", False)]


def test_a_quotation_that_never_closes_does_not_swallow_the_book() -> None:
    texts = ["“Mở rồi quên đóng"] + [f"Câu thường số {i}." for i in range(30)]
    states = quote_states(texts)
    assert states[1] and not states[-1]  # speech for a while, narration again well before the end


def test_stray_marks_and_empty_pieces_never_produce_empty_segments() -> None:
    for text in ['”Chỉ có dấu đóng', '“”', '"..."', "“Ừ.”", ""]:
        assert all(any(c.isalnum() for c in s.text) for s in split_sentence(text)[0])
