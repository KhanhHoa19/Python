"""Schemas of the administrator panel."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

from src.api.schemas.book_schemas import CategoryResponse
from src.api.schemas.voice_schemas import VoiceResponse

_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class AdminBookResponse(BaseModel):
    id: int
    title: str
    author: str
    total_chapters: int
    is_public: bool
    is_mine: bool  # uploaded by the admin who asks (only those can be published)
    category: CategoryResponse | None = None
    cover_url: str | None = None
    shelf_count: int = 0  # how many readers keep it on their shelf


class PublicRequest(BaseModel):
    is_public: bool


class CategoryAdminResponse(CategoryResponse):
    book_count: int = 0


class CategoryRequest(BaseModel):
    name: str = Field(max_length=80)
    icon: str = Field(default="book", max_length=40)
    color: str = "#8a6d3b"

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        trimmed = " ".join(value.split())
        if not trimmed:
            raise ValueError("Name must not be empty")
        return trimmed

    @field_validator("color")
    @classmethod
    def _color(cls, value: str) -> str:
        if not _COLOR.match(value):
            raise ValueError("Color must look like #a1b2c3")
        return value.lower()

    @field_validator("icon")
    @classmethod
    def _icon(cls, value: str) -> str:
        return value.strip() or "book"


class AdminVoicesResponse(BaseModel):
    voices: list[VoiceResponse]  # cloned voices the admin may publish, plus the already public ones
    default_voice: str = ""  # system default ("" = the one from .env)


class DefaultVoiceRequest(BaseModel):
    voice_id: str = Field(min_length=1, max_length=255)


class AdminUserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    created_at: str | None = None
    book_count: int = 0
    voice_count: int = 0
