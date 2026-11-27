"""Listening statistics (Pandas / NumPy) on fixed sample data."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from src.core.analytics.stats import daily_stats, latency_stats, voice_stats, words_per_minute

TODAY = date(2026, 11, 27)


def test_daily_stats_groups_sessions_by_day_and_fills_empty_days_with_zeros() -> None:
    rows = [
        (datetime(2026, 11, 27, 8, 0), 600, 1500),
        (datetime(2026, 11, 27, 21, 30), 300, 700),  # same day as the first: summed
        (datetime(2026, 11, 25, 12, 0), 1800, 4500),
    ]
    result = daily_stats(rows, days=4, today=TODAY)
    assert [d["date"] for d in result] == ["2026-11-24", "2026-11-25", "2026-11-26", "2026-11-27"]
    assert result[0] == {"date": "2026-11-24", "minutes": 0.0, "words": 0, "sessions": 0}  # nobody listened
    assert result[1] == {"date": "2026-11-25", "minutes": 30.0, "words": 4500, "sessions": 1}
    assert result[2]["sessions"] == 0
    assert result[3] == {"date": "2026-11-27", "minutes": 15.0, "words": 2200, "sessions": 2}


def test_daily_stats_reads_what_each_database_returns() -> None:
    """SQLite gives text timestamps, MySQL gives datetime and Decimal sums; both end up as plain numbers."""
    rows = [("2026-11-27 08:00:00", 120, 40), (datetime(2026, 11, 27, 9, 0), Decimal("60"), Decimal("20")),
            ("2026-11-27T10:00:00Z", 60, None)]
    today = daily_stats(rows, days=2, today=TODAY)[-1]
    assert today == {"date": "2026-11-27", "minutes": 4.0, "words": 60, "sessions": 3}
    assert isinstance(today["minutes"], float) and isinstance(today["words"], int)


def test_daily_stats_without_any_session_is_all_zeros_and_days_are_at_least_one() -> None:
    result = daily_stats([], days=3, today=TODAY)
    assert len(result) == 3 and all(d["minutes"] == 0.0 and d["sessions"] == 0 for d in result)
    assert len(daily_stats([], days=0, today=TODAY)) == 1


def test_sessions_older_than_the_window_are_not_counted() -> None:
    assert daily_stats([(datetime(2026, 1, 1), 600, 100)], days=7, today=TODAY)[-1]["minutes"] == 0.0


def test_voice_stats_sums_per_voice_longest_first_and_keeps_missing_voices() -> None:
    rows = [("a", 600, 100), ("b", 1800, 400), ("a", 600, 150), (None, 60, 10)]
    result = voice_stats(rows)
    assert [v["voice"] for v in result] == ["b", "a", ""]
    assert result[0] == {"voice": "b", "minutes": 30.0, "words": 400, "sessions": 1}
    assert result[1] == {"voice": "a", "minutes": 20.0, "words": 250, "sessions": 2}
    assert voice_stats([]) == []


def test_latency_stats_mean_p95_max_and_success_rate() -> None:
    result = latency_stats([0.5, 1.5, 1.0], ["SUCCESS", "SUCCESS", "FAILED"])
    assert result == {"total_calls": 3, "avg_latency_ms": 1000.0, "p95_latency_ms": 1500.0, "max_latency_ms": 1500.0, "success_rate": 66.7}
    assert latency_stats([], []) == {"total_calls": 0, "avg_latency_ms": 0.0, "p95_latency_ms": 0.0, "max_latency_ms": 0.0, "success_rate": 0.0}


def test_p95_is_a_latency_that_really_happened_and_ignores_the_status_case() -> None:
    latencies = [i / 100 for i in range(1, 101)]  # 10 ms ... 1000 ms
    result = latency_stats(latencies, ["success"] * 100)  # lower case counts as success too
    assert result["p95_latency_ms"] == 950.0 and result["success_rate"] == 100.0
    assert latency_stats([2.0], ["SUCCESS"])["p95_latency_ms"] == 2000.0


@pytest.mark.parametrize(("words", "minutes", "expected"), [(1500, 10, 150.0), (0, 10, 0.0), (500, 0, 0.0), (1000, 7.5, 133.3)])
def test_words_per_minute(words: float, minutes: float, expected: float) -> None:
    assert words_per_minute(words, minutes) == expected
