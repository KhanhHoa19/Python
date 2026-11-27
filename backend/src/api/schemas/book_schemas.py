"""Pydantic validation schemas for Book catalog and ingestion."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryResponse(BaseModel):
    id: int
    name: str
    slug: str
    icon: str
    color: str


class ProgressResponse(BaseModel):
    """One user's progress in a book (GET /api/books returns it with every book, so clients need no extra calls)."""

    status: Literal["unread", "reading", "completed"]
    is_favorite: bool
    current_chapter: int
    current_sentence_index: int
    completion_percentage: float
    last_read_at: str | None = None
    voice: str | None = None


class BookSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author: str
    total_chapters: int
    total_sentences: int
    total_words: int
    created_at: str | None = None
    is_public: bool = False  # a system book shared with everyone
    is_mine: bool = True  # False for a public book uploaded by someone else
    on_shelf: bool = True  # the book is on the caller's shelf (always true for their own books)
    category: CategoryResponse | None = None
    cover_url: str | None = None  # relative URL, e.g. /api/covers/<name>.jpg (readable without a token)
    progress: ProgressResponse | None = None  # None = the caller never opened it


class BookDetailResponse(BookSummaryResponse):
    source_path: str
    content_hash: str


MAX_TITLE_LENGTH = 255  # books.title is VARCHAR(255)


class BookRenameRequest(BaseModel):
    title: str = Field(max_length=MAX_TITLE_LENGTH * 4)  # real limit is checked after trimming

    @field_validator("title")
    @classmethod
    def _trimmed_title(cls, value: str) -> str:
        trimmed = " ".join(value.split())  # trim and collapse inner whitespace
        if not trimmed:
            raise ValueError("Title must not be empty")
        if len(trimmed) > MAX_TITLE_LENGTH:
            raise ValueError(f"Title must be at most {MAX_TITLE_LENGTH} characters")
        return trimmed


class BookUpdateRequest(BaseModel):
    """Change a book's title, author and/or category. Only the fields that are sent change (`category_id: null` clears it)."""

    title: str | None = Field(default=None, max_length=MAX_TITLE_LENGTH * 4)
    author: str | None = Field(default=None, max_length=MAX_TITLE_LENGTH * 2)
    category_id: int | None = None

    @field_validator("author")
    @classmethod
    def _trimmed_author(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = " ".join(value.split())
        if len(trimmed) > MAX_TITLE_LENGTH:
            raise ValueError(f"Author must be at most {MAX_TITLE_LENGTH} characters")
        return trimmed

    @field_validator("title")
    @classmethod
    def _trimmed_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = " ".join(value.split())
        if not trimmed:
            raise ValueError("Title must not be empty")
        if len(trimmed) > MAX_TITLE_LENGTH:
            raise ValueError(f"Title must be at most {MAX_TITLE_LENGTH} characters")
        return trimmed


class FavoriteRequest(BaseModel):
    is_favorite: bool


class StatusRequest(BaseModel):
    status: Literal["completed", "unread"]  # "Đánh dấu đã nghe xong" / "Nghe lại từ đầu"


class ShelfCountsResponse(BaseModel):
    unread: int
    reading: int
    completed: int
    favorite: int


class BookSentenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sentence_index: int
    chapter_index: int
    text_content: str
    word_count: int


class BookSentencesListResponse(BaseModel):
    book_id: int
    total_sentences: int
    sentences: list[BookSentenceResponse]


class BookUploadSuccessResponse(BaseModel):
    status: str = "success"
    book_id: int
    title: str
    total_chapters: int
    total_sentences: int
    total_words: int


class ChapterResponse(BaseModel):
    chapter_index: int
    title: str
    start_sentence_index: int
    end_sentence_index: int
    sentence_count: int
    word_count: int


class BookChaptersResponse(BaseModel):
    book_id: int
    chapters: list[ChapterResponse]
