"""Listening statistics with Pandas and NumPy.

The repositories only read raw rows from the database; everything that is arithmetic over them lives here, as
pure functions (no database, no clock: the caller passes `today`), so they are easy to test with fixed data.

- Pandas: group sessions by day or by voice (`groupby`), and fill the days with no listening with zeros (`reindex`).
- NumPy: average, maximum and 95th percentile of the TTS latency."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from typing import Any

import numpy as np
import pandas as pd


def _sessions_frame(rows: Iterable[Sequence[Any]], columns: list[str]) -> pd.DataFrame:
    """Rows from the database as a DataFrame with numeric columns. MySQL hands back Decimal for sums: converted here."""
    frame = pd.DataFrame(list(rows), columns=columns)
    for name in columns:
        if name not in ("start", "voice"):
            frame[name] = pd.to_numeric(frame[name], errors="coerce").fillna(0.0).astype(float)
    return frame


def daily_stats(rows: Iterable[Sequence[Any]], days: int, today: date) -> list[dict[str, Any]]:
    """One row per calendar day for the last `days` days ending `today`, zero-filled.

    `rows`: (start_time, duration_seconds, words_read) of each reading session."""
    days = max(1, days)
    frame = _sessions_frame(rows, ["start", "seconds", "words"])
    index = pd.date_range(end=pd.Timestamp(today), periods=days, freq="D")
    if frame.empty:
        per_day = pd.DataFrame(0.0, index=index, columns=["seconds", "words", "sessions"])
    else:
        frame["day"] = pd.to_datetime(frame["start"], utc=True, format="mixed").dt.tz_localize(None).dt.normalize()
        per_day = (
            frame.groupby("day")
            .agg(seconds=("seconds", "sum"), words=("words", "sum"), sessions=("seconds", "size"))
            .reindex(index, fill_value=0)  # the days nobody listened
        )
    return [
        {"date": day.date().isoformat(), "minutes": round(float(r.seconds) / 60.0, 1),
         "words": int(r.words), "sessions": int(r.sessions)}
        for day, r in per_day.iterrows()
    ]


def voice_stats(rows: Iterable[Sequence[Any]]) -> list[dict[str, Any]]:
    """Listening time per voice, longest first; a session without a voice is the voice "".

    `rows`: (voice, duration_seconds, words_read) of each reading session."""
    frame = _sessions_frame(rows, ["voice", "seconds", "words"])
    if frame.empty:
        return []
    frame["voice"] = frame["voice"].fillna("")
    per_voice = (
        frame.groupby("voice")
        .agg(seconds=("seconds", "sum"), words=("words", "sum"), sessions=("seconds", "size"))
        .sort_values("seconds", ascending=False)
    )
    return [
        {"voice": str(voice), "minutes": round(float(r.seconds) / 60.0, 1), "words": int(r.words), "sessions": int(r.sessions)}
        for voice, r in per_voice.iterrows()
    ]


def latency_stats(latencies_seconds: Sequence[float], statuses: Sequence[str]) -> dict[str, Any]:
    """Average, 95th percentile and maximum latency in milliseconds, and the share of successful calls (percent).

    The 95th percentile is the nearest recorded value, so it is always a latency that really happened."""
    if len(latencies_seconds) == 0:
        return {"total_calls": 0, "avg_latency_ms": 0.0, "p95_latency_ms": 0.0, "max_latency_ms": 0.0, "success_rate": 0.0}
    millis = np.asarray(latencies_seconds, dtype=float) * 1000.0
    ok = np.char.upper(np.asarray(statuses, dtype=str)) == "SUCCESS"
    return {
        "total_calls": int(millis.size),
        "avg_latency_ms": round(float(np.mean(millis)), 1),
        "p95_latency_ms": round(float(np.percentile(millis, 95, method="nearest")), 1),
        "max_latency_ms": round(float(np.max(millis)), 1),
        "success_rate": round(float(np.mean(ok)) * 100.0, 1),
    }


def words_per_minute(words: float, minutes: float) -> float:
    """Average listening speed; 0 when there is no listening time."""
    return round(float(words) / float(minutes), 1) if minutes else 0.0
