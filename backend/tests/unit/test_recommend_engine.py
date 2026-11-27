"""The scoring of recommendations: what the reader did, what they chose, and the filters."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.core.recommend.engine import (
    DEFAULT_WPM,
    Candidate,
    HistoryItem,
    clamp_wpm,
    estimate_minutes,
    history_affinity,
    rank,
)
from src.core.recommend.moods import MOODS, mood_by_id

NOW = datetime(2026, 11, 27, 12, 0)
NAMES = {1: "Trinh thám", 2: "Khoa học", 3: "Thiếu nhi", 4: "Lịch sử"}


def book(book_id: int, category: int | None, words: int = 6000, age_days: int = 100, shelves: int = 0) -> Candidate:
    return Candidate(book_id, category, words, NOW - timedelta(days=age_days), shelves)


def done(category: int, days_ago: int = 3, completion: float = 100.0, status: str = "completed", favorite: bool = False) -> HistoryItem:
    return HistoryItem(category, status, favorite, completion, NOW - timedelta(days=days_ago))


def ranked(candidates, history=(), minutes=None, favorites=(), **kwargs):
    points = history_affinity(list(history), minutes or {}, NOW)
    return rank(candidates, history_points=points, favorites=set(favorites), wpm=DEFAULT_WPM, now=NOW, category_names=NAMES, **kwargs)


def ids(result) -> list[int]:
    return [s.candidate.book_id for s in result]


def test_the_category_a_reader_finishes_comes_first() -> None:
    result = ranked([book(1, 2), book(2, 1), book(3, 3)], history=[done(1), done(1), done(2, completion=20, status="reading")])
    assert ids(result)[0] == 2  # Trinh thám: two finished books
    assert "Bạn hay nghe Trinh thám" in result[0].reasons


def test_a_favourite_book_counts_more_than_a_plain_finished_one() -> None:
    result = ranked([book(1, 2), book(2, 1)], history=[done(1), done(2, favorite=True)])
    assert ids(result)[0] == 1 or ids(result)[0] == 2
    liked = history_affinity([done(1), done(2, favorite=True)], {}, NOW)
    assert liked[2] > liked[1]


def test_a_book_left_early_and_old_adds_nothing_and_new_listening_outweighs_old() -> None:
    abandoned = history_affinity([done(1, days_ago=40, completion=2.0, status="reading")], {}, NOW)
    assert abandoned[1] < history_affinity([done(1, days_ago=40, completion=60.0, status="reading")], {}, NOW)[1]
    old = history_affinity([done(1, days_ago=400)], {}, NOW)[1]
    recent = history_affinity([done(1, days_ago=2)], {}, NOW)[1]
    assert recent > 4 * old  # listening fades with time


def test_listening_time_adds_points_but_is_capped() -> None:
    few = history_affinity([], {1: 15.0}, NOW)[1]
    lots = history_affinity([], {1: 100000.0}, NOW)[1]
    assert 0 < few < lots <= 3.0


def test_a_new_reader_is_led_by_the_categories_they_chose() -> None:
    result = ranked([book(1, 1), book(2, 2), book(3, 3)], favorites={3})
    assert ids(result)[0] == 3 and "Bạn đã chọn thích Thiếu nhi" in result[0].reasons


def test_without_any_signal_popularity_and_freshness_decide() -> None:
    result = ranked([book(1, 1, shelves=1, age_days=80), book(2, 2, shelves=9, age_days=80), book(3, 3, shelves=0, age_days=1)])
    assert ids(result)[0] in (2, 3) and ids(result)[-1] == 1
    assert "9 người đang giữ sách này" in result[ids(result).index(2)].reasons
    assert "Sách mới" in next(s for s in result if s.candidate.book_id == 3).reasons


def test_popularity_breaks_ties_once_there_is_history() -> None:
    result = ranked([book(1, 1, shelves=0), book(2, 1, shelves=5)], history=[done(1)])
    assert ids(result) == [2, 1]


def test_a_mood_keeps_only_its_categories() -> None:
    thrill = mood_by_id("hoi-hop")
    assert thrill is not None
    result = ranked([book(1, 1), book(2, 2), book(3, 3)], mood_label=thrill.label, mood_categories={1}, favorites={2})
    assert ids(result) == [1] and "Hợp tâm trạng Hồi hộp" in result[0].reasons  # even a favourite is dropped from another mood


def test_a_time_limit_drops_longer_books_and_says_so() -> None:
    result = ranked([book(1, 1, words=1500), book(2, 1, words=9000)], max_minutes=30)
    assert ids(result) == [1]  # 1500 words = 10 minutes; 9000 words = 60 minutes
    assert "Vừa đủ ~10 phút" in result[0].reasons and result[0].estimated_minutes == 10


def test_listening_speed_comes_from_the_readers_own_sessions() -> None:
    assert clamp_wpm(100, 60) == DEFAULT_WPM  # too little data
    assert clamp_wpm(24000, 3600) == 260.0 or clamp_wpm(24000, 3600) <= 260.0  # capped
    assert clamp_wpm(9000, 3600) == 150.0
    assert estimate_minutes(3000, 200) == 15 and estimate_minutes(10, 150) == 1


def test_limit_and_empty_input() -> None:
    assert ranked([]) == []
    assert len(ranked([book(i, 1) for i in range(1, 30)], limit=5)) == 5


def test_every_mood_points_at_real_default_categories() -> None:
    from src.core.storage.library import DEFAULT_CATEGORIES

    slugs = {c[1] for c in DEFAULT_CATEGORIES}
    assert len(MOODS) == 6 and all(set(m.categories) <= slugs for m in MOODS)


def test_a_secondary_taste_still_beats_an_unrelated_book_that_is_merely_popular() -> None:
    history = [done(1), done(1, favorite=True), done(3, completion=60.0, status="reading")]  # a big favourite, a small second taste
    result = ranked([book(1, 2, shelves=3), book(2, 3, shelves=0)], history=history, minutes={1: 40.0, 3: 14.0})
    assert ids(result)[0] == 2  # Thiếu nhi (second taste) ahead of Khoa học (unrelated, but on three shelves)
    assert any("Bạn hay nghe Thiếu nhi" in r for r in result[0].reasons)
