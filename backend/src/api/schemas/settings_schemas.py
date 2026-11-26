"""Pydantic schemas for application settings."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SettingsUpdateRequest(BaseModel):
    prefetch_count: int = Field(ge=1, le=5)
    default_speed: float = Field(ge=0.5, le=3.0)
    default_voice: str = Field(min_length=1, max_length=255)
    daily_char_limit: int = Field(ge=0)


class SettingsResponse(SettingsUpdateRequest):
    chars_used_today: int
    provider: str
