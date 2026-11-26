"""Pydantic schemas for audio notes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NoteCreateRequest(BaseModel):
    book_id: int
    sentence_index: int = Field(ge=0)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    note_text: str = Field(default="", max_length=5000)


class NoteUpdateRequest(BaseModel):
    note_text: str = Field(max_length=5000)


class NoteResponse(BaseModel):
    id: int
    book_id: int
    book_title: str
    sentence_index: int
    start_offset: int
    end_offset: int
    excerpt: str
    note_text: str
    created_at: str
