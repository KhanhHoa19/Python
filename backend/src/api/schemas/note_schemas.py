"""Pydantic schemas for favourite quotes (stored in the audio_notes table)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

EmotionTag = Literal["inspiring", "touching", "wise", "funny"]


class NoteCreateRequest(BaseModel):
    """A quote: a highlighted part of a sentence (give both offsets) or the WHOLE sentence (give neither: the one-tap bookmark)."""

    book_id: int
    sentence_index: int = Field(ge=0)
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, gt=0)
    note_text: str = Field(default="", max_length=5000)
    emotion_tag: EmotionTag | None = None
    voice: str | None = Field(default=None, max_length=255)  # the voice of the saved audio; default: the user's own

    @model_validator(mode="after")
    def _both_or_neither_offset(self) -> NoteCreateRequest:
        if (self.start_offset is None) != (self.end_offset is None):
            raise ValueError("Give both start_offset and end_offset, or neither for the whole sentence.")
        return self


class NoteUpdateRequest(BaseModel):
    """Only the fields that are sent change; `emotion_tag: null` removes the tag."""

    note_text: str | None = Field(default=None, max_length=5000)
    emotion_tag: EmotionTag | None = None


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
    emotion_tag: EmotionTag | None = None
    context_before: str = ""
    context_after: str = ""
    has_audio: bool = False  # a copy of the audio is saved for good (it survives clearing the cache)
    voice: str | None = None
