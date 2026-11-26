"""Pydantic schemas for audio export."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExportRequest(BaseModel):
    from_index: int = Field(default=0, ge=0)
    to_index: int | None = Field(default=None, ge=0)
    voice: str | None = None
    speed: float = Field(default=1.0, ge=0.5, le=3.0)
    format: Literal["wav", "mp3"] | None = None


class ExportEstimateResponse(BaseModel):
    sentences: int
    words: int
    estimated_minutes: float
    chars_to_synthesize: int
    chars_cached: int
    daily_limit: int
    chars_used_today: int


class ExportJobResponse(BaseModel):
    job_id: str
    status: Literal["running", "done", "failed"]
    done: int
    total: int
    file_name: str | None = None
    error: str | None = None
