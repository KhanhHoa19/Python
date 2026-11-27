"""Scoring of books for one reader. Pure functions: no database, no clock (the caller passes `now`).

What goes into a score
- Affinity: how much the reader likes the book's category. It is built from their history (time listened, finished,
  favourite, left unfinished = negative, fading with age) plus the categories they chose themselves.
- Popularity: how many people keep the book on their shelf (an aggregate number, never who).
- Freshness: newer books score a little higher.
A reader with history gets a mix of all three; a new reader who only picked favourite categories leans on those and
on popularity; with neither signal, popularity and freshness decide.

Hard filters: a mood keeps only books of its categories; a time limit drops books that would take longer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

DEFAULT_WPM = 150.0  # words per minute while listening, until the reader has enough history of their own
MIN_WPM, MAX_WPM = 80.0, 260.0
HALF_LIFE_DAYS = 60.0  # an old listen counts half as much every two months
ABANDON_DAYS = 14
FAVORITE_BOOST = 4.0  # a category the reader chose by hand
MINUTES_PER_POINT = 30.0  # 30 minutes listened in a category = 1 point (capped)
MINUTES_CAP_POINTS = 3.0
FRESH_DAYS = 90.0
NEW_BADGE_DAYS = 14.0


@dataclass(frozen=True)
class HistoryItem:
    """One book on the reader's shelf, as far as scoring cares."""

    category_id: int | None
    status: str  # unread | reading | completed
    is_favorite: bool
    completion: float  # 0-100
    last_read_at: datetime | None


@dataclass(frozen=True)
class Candidate:
    book_id: int
    category_id: int | None
    words: int
    created_at: datetime | None
    shelf_count: int  # how many readers keep it on their shelf


@dataclass
class Scored:
    candidate: Candidate
    score: float
    estimated_minutes: int
    reasons: list[str] = field(default_factory=list)


def clamp_wpm(words: int, seconds: float) -> float:
    """Listening speed in words per minute from the reader's sessions; the default when there is too little data."""
    if seconds < 300 or words <= 0:
        return DEFAULT_WPM
    return min(max(words / (seconds / 60.0), MIN_WPM), MAX_WPM)


def estimate_minutes(words: int, wpm: float) -> int:
    return max(1, round(words / max(wpm, 1.0)))


def _age_days(moment: datetime | None, now: datetime) -> float | None:
    if moment is None:
        return None
    return max(0.0, (now - moment.replace(tzinfo=None)).total_seconds() / 86400.0)


def history_affinity(
    history: list[HistoryItem], minutes_by_category: dict[int, float], now: datetime,
) -> dict[int, float]:
    """Raw (unnormalised) points per category from what the reader actually did."""
    points: dict[int, float] = {}
    for item in history:
        if item.category_id is None:
            continue
        weight = 0.5 + item.completion / 100.0 * 2.0
        if item.status == "completed":
            weight += 2.0
        if item.is_favorite:
            weight += 3.0
        age = _age_days(item.last_read_at, now)
        if item.status != "completed" and item.completion < 10.0 and age is not None and age > ABANDON_DAYS:
            weight -= 1.5  # tried it and left
        if age is not None:
            weight *= 0.5 ** (age / HALF_LIFE_DAYS)
        points[item.category_id] = points.get(item.category_id, 0.0) + max(weight, 0.0)
    for category_id, minutes in minutes_by_category.items():
        points[category_id] = points.get(category_id, 0.0) + min(minutes / MINUTES_PER_POINT, MINUTES_CAP_POINTS)
    return points


def normalise(points: dict[int, float]) -> dict[int, float]:
    """0-1 share of the strongest category, on a square-root scale: a secondary taste (a third of the top one's points)
    still counts for well over half of it, instead of being drowned by the reader's one big favourite."""
    top = max(points.values(), default=0.0)
    return {k: (v / top) ** 0.5 for k, v in points.items()} if top > 0 else {}


def rank(
    candidates: list[Candidate], *, history_points: dict[int, float], favorites: set[int], wpm: float, now: datetime,
    category_names: dict[int, str], mood_label: str | None = None, mood_categories: set[int] | None = None,
    max_minutes: int | None = None, limit: int = 12,
) -> list[Scored]:
    """The candidates best first, each with its reasons. Filters (mood, time limit) are applied before scoring."""
    liked = normalise(history_points)
    points = dict(history_points)
    for category_id in favorites:
        points[category_id] = points.get(category_id, 0.0) + FAVORITE_BOOST
    affinity = normalise(points)
    has_history = bool(history_points)
    has_signal = bool(affinity)
    if has_history:
        w_aff, w_pop, w_fresh = 0.62, 0.10, 0.08
    elif has_signal:
        w_aff, w_pop, w_fresh = 0.55, 0.25, 0.10
    else:
        w_aff, w_pop, w_fresh = 0.0, 0.60, 0.40

    top_shelf = max((c.shelf_count for c in candidates), default=0)
    scored: list[Scored] = []
    for c in candidates:
        if mood_categories is not None and c.category_id not in mood_categories:
            continue
        minutes = estimate_minutes(c.words, wpm)
        if max_minutes is not None and minutes > max_minutes:
            continue
        age = _age_days(c.created_at, now)
        fresh = 0.0 if age is None else max(0.0, 1.0 - min(age, FRESH_DAYS) / FRESH_DAYS)
        popularity = c.shelf_count / top_shelf if top_shelf else 0.0
        a = affinity.get(c.category_id, 0.0) if c.category_id is not None else 0.0
        item = Scored(c, w_aff * a + w_pop * popularity + w_fresh * fresh, minutes)
        cid = c.category_id
        name = category_names.get(cid) if cid is not None else None
        if cid is not None and name:
            if cid in favorites:
                item.reasons.append(f"Bạn đã chọn thích {name}")
            if liked.get(cid, 0.0) >= 0.3:
                item.reasons.append(f"Bạn hay nghe {name}")
        if mood_label:
            item.reasons.append(f"Hợp tâm trạng {mood_label}")
        if max_minutes is not None:
            item.reasons.append(f"Vừa đủ ~{minutes} phút")
        if c.shelf_count >= 2:
            item.reasons.append(f"{c.shelf_count} người đang giữ sách này")
        if age is not None and age <= NEW_BADGE_DAYS:
            item.reasons.append("Sách mới")
        scored.append(item)
    scored.sort(key=lambda s: (-s.score, -s.candidate.shelf_count, -s.candidate.book_id))
    return scored[:limit]
