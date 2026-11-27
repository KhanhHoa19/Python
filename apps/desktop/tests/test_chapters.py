"""Table-of-contents helpers shared with the web app."""

from __future__ import annotations

from player.chapters import chapter_at, describe_chapter


def _chapter(number: int, start: int, end: int) -> dict:
    return {"chapter_index": number, "title": f"Chương {number}", "start_sentence_index": start,
            "end_sentence_index": end, "sentence_count": end - start + 1, "word_count": 10}


CHAPTERS = [_chapter(1, 0, 4), _chapter(2, 5, 9), _chapter(3, 10, 10)]


def test_chapter_at_includes_first_and_last_sentence() -> None:
    assert [chapter_at(CHAPTERS, i)["chapter_index"] for i in (0, 4, 5, 9, 10)] == [1, 1, 2, 2, 3]


def test_chapter_at_falls_back_to_nearest_and_none() -> None:
    assert chapter_at(CHAPTERS, -3)["chapter_index"] == 1
    assert chapter_at(CHAPTERS, 99)["chapter_index"] == 3
    assert chapter_at([], 0) is None


def test_describe_chapter() -> None:
    assert describe_chapter(CHAPTERS[0], str) == "5 câu · 10 từ"
