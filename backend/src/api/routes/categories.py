"""Book categories (the list in the sidebar)."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.schemas.book_schemas import CategoryResponse
from src.core.storage.db import get_db_engine
from src.core.storage.repositories import SqlCategoryRepository

router = APIRouter(tags=["categories"])


@router.get("", response_model=list[CategoryResponse])
def list_categories() -> list[CategoryResponse]:
    return [CategoryResponse(**c) for c in SqlCategoryRepository(get_db_engine()).list_all()]
