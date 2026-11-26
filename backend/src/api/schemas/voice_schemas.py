"""Pydantic schemas for voices."""

from __future__ import annotations

from pydantic import BaseModel


class VoiceResponse(BaseModel):
    voice_id: str
    display_name: str
    provider: str
    language: str = ""
    gender: str | None = None
    style: str | None = None
    is_custom: bool = False
    consent_at: str | None = None


class VoiceListResponse(BaseModel):
    provider: str
    supports_cloning: bool
    voices: list[VoiceResponse]
    warning: str | None = None
