"""MySQL returns Decimal for SUM()/AVG(); repositories must still produce plain numbers."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from src.core.storage.repositories import SqlSessionRepository, SqlTelemetryRepository


class _Result:
    def __init__(self, rows: list[tuple[Any, ...]]):
        self._rows = rows

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._rows[0] if self._rows else None


class _Conn:
    def __init__(self, results: list[list[tuple[Any, ...]]]):
        self._results = list(results)

    def __enter__(self) -> _Conn:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, *args: object, **kwargs: object) -> _Result:
        return _Result(self._results.pop(0))


class _Engine:
    def __init__(self, *results: list[tuple[Any, ...]]):
        self._results = list(results)

    def connect(self) -> _Conn:
        return _Conn(self._results)


def test_daily_stats_accepts_decimal_sums() -> None:
    today = datetime.now(UTC).date().isoformat()
    engine = _Engine([(today, Decimal("120"), Decimal("40"), 2)])
    days = SqlSessionRepository(engine).get_daily_stats(days=2)  # type: ignore[arg-type]
    assert days[-1] == {"date": today, "minutes": 2.0, "words": 40, "sessions": 2}
    assert isinstance(days[-1]["minutes"], float) and isinstance(days[-1]["words"], int)


def test_aggregated_metrics_accepts_decimal_sums() -> None:
    engine = _Engine([(Decimal("180"), Decimal("55"), 3)], [(0.5, None, None)])
    result = SqlTelemetryRepository(engine).get_aggregated_metrics()  # type: ignore[arg-type]
    assert result["total_listening_minutes"] == 3.0
    assert result["total_words_absorbed"] == 55 and result["total_sessions"] == 3
