"""Pydantic schemas for voices."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class VoiceResponse(BaseModel):
    voice_id: str
    display_name: str
    provider: str
    language: str = ""
    gender: str | None = None
    style: str | None = None
    is_custom: bool = False
    consent_at: str | None = None
    is_public: bool = False  # a system voice shared with everyone
    is_mine: bool = False  # a voice the caller cloned (provider voices are nobody's)


class VoiceRenameRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("display_name")
    @classmethod
    def _trimmed(cls, value: str) -> str:
        trimmed = " ".join(value.split())
        if not trimmed:
            raise ValueError("Name must not be empty")
        return trimmed


class VoiceListResponse(BaseModel):
    provider: str
    supports_cloning: bool
    clone_sample_seconds: tuple[float, float] = (5.0, 15.0)
    voices: list[VoiceResponse]
    warning: str | None = None
    my_voice_count: int = 0  # voices the caller cloned
    max_voices: int | None = None  # None = unlimited (admins)
    system_default_voice: str = ""
