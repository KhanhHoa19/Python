"""Schemas of the recommendation tab."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.api.schemas.book_schemas import BookSummaryResponse


class RecommendedBook(BookSummaryResponse):
    reasons: list[str] = []  # why it was suggested, ready to show
    estimated_minutes: int = 0  # at this reader's own listening speed


class MoodResponse(BaseModel):
    id: str
    label: str
    categories: list[str]  # category slugs


class TopCategory(BaseModel):
    slug: str
    name: str
    weight: float  # 0-1 share of the strongest one


class RecommendationsResponse(BaseModel):
    items: list[RecommendedBook]
    moods: list[MoodResponse]
    favorite_categories: list[str]  # slugs the reader chose
    onboarded: bool  # has answered (or skipped) the first-time question
    has_history: bool
    top_categories: list[TopCategory]  # what their history says they like


class PreferencesRequest(BaseModel):
    favorite_categories: list[str] = Field(default_factory=list, max_length=15)
    onboarded: bool = True
