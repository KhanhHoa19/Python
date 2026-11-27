"""Schemas of the background-sound library."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class AmbientTrackResponse(BaseModel):
    id: int
    name: str
    url: str  # relative, readable without a token (an <audio> element cannot send one)
    size_bytes: int = 0


class AmbientRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def _trimmed(cls, value: str) -> str:
        trimmed = " ".join(value.split())
        if not trimmed:
            raise ValueError("Name must not be empty")
        return trimmed
