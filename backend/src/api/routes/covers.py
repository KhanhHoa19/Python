"""Cover images. Public on purpose: an <img> tag cannot send a token, and the file name is a random 128-bit id."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.core.ingestion.covers import cover_path

router = APIRouter(tags=["covers"])


@router.get("/covers/{name}")
def get_cover(name: str) -> FileResponse:
    path = cover_path(name)
    if path is None:
        raise HTTPException(404, "Cover not found")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
