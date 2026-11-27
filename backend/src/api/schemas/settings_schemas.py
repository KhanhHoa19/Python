"""Pydantic schemas for application settings."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SettingsUpdateRequest(BaseModel):
    prefetch_count: int = Field(ge=1, le=5)
    default_speed: float = Field(ge=0.5, le=3.0)
    default_voice: str = Field(min_length=1, max_length=255)
    daily_char_limit: int = Field(ge=0)
    # Optional: a client that does not know them (older desktop build) leaves the saved choice alone.
    ambient_track: int | None = Field(default=None, ge=0)
    ambient_volume: float | None = Field(default=None, ge=0.0, le=1.0)
    chapter_chime: bool | None = None


class SettingsResponse(BaseModel):
    prefetch_count: int
    default_speed: float
    default_voice: str
    daily_char_limit: int
    ambient_track: int = 0  # 0 = no background sound
    ambient_volume: float = 0.4
    chapter_chime: bool = True
    chars_used_today: int
    provider: str
