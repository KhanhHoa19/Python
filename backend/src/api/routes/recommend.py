"""Recommendations: public books the reader has not shelved yet, ranked for them, with the reasons."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import current_user
from src.api.schemas.book_schemas import CategoryResponse
from src.api.schemas.recommend_schemas import (
    MoodResponse,
    PreferencesRequest,
    RecommendationsResponse,
    RecommendedBook,
    TopCategory,
)
from src.core.auth.users import User
from src.core.ingestion.covers import cover_url
from src.core.recommend.engine import (
    Candidate,
    HistoryItem,
    clamp_wpm,
    history_affinity,
    normalise,
    rank,
)
from src.core.recommend.moods import MOODS, mood_by_id
from src.core.storage.db import get_db_engine
from src.core.storage.repositories import (
    SqlCategoryRepository,
    SqlRecommendRepository,
    SqlUserSettingsRepository,
)

router = APIRouter(tags=["recommendations"])

FAVORITES_KEY = "favorite_categories"
ONBOARDED_KEY = "recommend_onboarded"
MAX_LIMIT = 50


def _favorites(settings: SqlUserSettingsRepository) -> list[str]:
    return [s for s in (settings.get(FAVORITES_KEY, "") or "").split(",") if s]


@router.get("", response_model=RecommendationsResponse)
def recommendations(
    mood: str | None = None, max_minutes: int | None = None, limit: int = 12, user: User = Depends(current_user),
) -> RecommendationsResponse:
    """Suggestions for the caller. `mood` keeps one mood's categories; `max_minutes` drops books that take longer."""
    engine = get_db_engine()
    chosen_mood = mood_by_id(mood) if mood else None
    if mood and chosen_mood is None:
        raise HTTPException(400, f"Unknown mood '{mood}'")
    if max_minutes is not None and max_minutes < 1:
        raise HTTPException(400, "max_minutes must be at least 1")

    categories = SqlCategoryRepository(engine).list_all()
    by_slug = {c["slug"]: c for c in categories}
    by_id = {c["id"]: c for c in categories}
    settings = SqlUserSettingsRepository(engine, user.id)
    favorite_slugs = [s for s in _favorites(settings) if s in by_slug]
    favorites = {by_slug[s]["id"] for s in favorite_slugs}

    repo = SqlRecommendRepository(engine, user.id)
    now = datetime.now(UTC).replace(tzinfo=None)
    history = [HistoryItem(**h) for h in repo.history()]
    points = history_affinity(history, repo.minutes_by_category(), now)
    words, seconds = repo.listening_totals()
    pairs = repo.candidates()
    books = {b.id: b for b, _ in pairs}
    ranked = rank(
        [Candidate(b.id or 0, b.category_id, b.total_words, SqlRecommendRepository._moment(b.created_at), shelf) for b, shelf in pairs],
        history_points=points, favorites=favorites, wpm=clamp_wpm(words, seconds), now=now,
        category_names={c["id"]: c["name"] for c in categories},
        mood_label=chosen_mood.label if chosen_mood else None,
        mood_categories={by_slug[s]["id"] for s in chosen_mood.categories if s in by_slug} if chosen_mood else None,
        max_minutes=max_minutes, limit=min(max(limit, 1), MAX_LIMIT),
    )

    items = []
    for scored in ranked:
        book = books[scored.candidate.book_id]
        category = by_id.get(book.category_id) if book.category_id is not None else None
        items.append(RecommendedBook(
            id=book.id or 0, title=book.title, author=book.author, total_chapters=book.total_chapters,
            total_sentences=book.total_sentences, total_words=book.total_words,
            created_at=book.created_at.isoformat() if isinstance(book.created_at, datetime) else (str(book.created_at) if book.created_at else None),
            is_public=True, is_mine=False, on_shelf=False,
            category=CategoryResponse(**category) if category else None, cover_url=cover_url(book.cover_path),
            reasons=scored.reasons, estimated_minutes=scored.estimated_minutes,
        ))
    liked = normalise(points)
    top = sorted(liked.items(), key=lambda kv: -kv[1])[:3]
    return RecommendationsResponse(
        items=items,
        moods=[MoodResponse(id=m.id, label=m.label, categories=list(m.categories)) for m in MOODS],
        favorite_categories=favorite_slugs,
        onboarded=bool(settings.get(ONBOARDED_KEY, "")) or bool(favorite_slugs),
        has_history=bool(history) or repo.session_count() > 0,
        top_categories=[TopCategory(slug=by_id[i]["slug"], name=by_id[i]["name"], weight=round(w, 2)) for i, w in top if i in by_id],
    )


@router.put("/preferences", response_model=RecommendationsResponse)
def save_preferences(req: PreferencesRequest, user: User = Depends(current_user)) -> RecommendationsResponse:
    """Choose (or change) the topic tags the reader likes. An empty list is allowed: "I will let my history decide"."""
    engine = get_db_engine()
    known = {c["slug"] for c in SqlCategoryRepository(engine).list_all()}
    unknown = [s for s in req.favorite_categories if s not in known]
    if unknown:
        raise HTTPException(400, f"Unknown categories: {', '.join(unknown)}")
    settings = SqlUserSettingsRepository(engine, user.id)
    settings.set(FAVORITES_KEY, ",".join(dict.fromkeys(req.favorite_categories)))  # no duplicates, order kept
    settings.set(ONBOARDED_KEY, "1" if req.onboarded else "")
    return recommendations(user=user)
