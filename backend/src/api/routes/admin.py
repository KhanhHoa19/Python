"""Administrator panel: system books, categories, system voices, the default voice and the user list.

Every route needs `role=admin`. An admin still cannot read another person's private books or notes:
they may only publish what they own and manage what is already public."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import Engine, text

from src.api.deps import require_admin
from src.api.routes.ambient import track_response
from src.api.schemas.admin_schemas import (
    AdminBookResponse,
    AdminUserResponse,
    AdminVoicesResponse,
    CategoryAdminResponse,
    CategoryRequest,
    DefaultVoiceRequest,
    PublicRequest,
)
from src.api.schemas.ambient_schemas import AmbientRenameRequest, AmbientTrackResponse
from src.api.schemas.book_schemas import CategoryResponse
from src.api.schemas.voice_schemas import VoiceResponse
from src.core.audio.ambient import (
    MAX_AMBIENT_BYTES,
    AmbientError,
    delete_ambient_file,
    save_ambient,
)
from src.core.auth.users import SqlUserRepository, User
from src.core.ingestion.covers import cover_url
from src.core.storage.db import get_db_engine
from src.core.storage.repositories import (
    SqlAmbientRepository,
    SqlBookRepository,
    SqlCategoryRepository,
    SqlSettingsRepository,
    SqlVoiceRepository,
)
from src.core.tts.base import TTSProviderError
from src.core.tts.factory import TTSFactory

router = APIRouter(tags=["admin"], dependencies=[Depends(require_admin)])

PROTECTED_SLUG = "khac"  # where books without a category go: it cannot be removed


def _slug(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name.replace("đ", "d").replace("Đ", "D"))
    plain = "".join(c for c in plain if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-") or "the-loai"


# ------------------------------------------------------------------------------------------------ books

@router.get("/books", response_model=list[AdminBookResponse])
def list_system_books(admin: User = Depends(require_admin)) -> list[AdminBookResponse]:
    """Public books, plus the admin's own private books (candidates to publish). Nobody else's private books."""
    engine = get_db_engine()
    categories = {c["id"]: c for c in SqlCategoryRepository(engine).list_all()}
    repo = SqlBookRepository(engine)
    entries = repo.list_public_with_shelves()
    shown = {b.id for b, _ in entries}
    entries += [(b, 0) for b in repo.list_books(limit=500, user_id=admin.id) if b.owner_id == admin.id and b.id not in shown]
    return [
        AdminBookResponse(
            id=b.id or 0, title=b.title, author=b.author, total_chapters=b.total_chapters, is_public=b.is_public,
            is_mine=b.owner_id == admin.id,
            category=CategoryResponse(**categories[b.category_id]) if b.category_id in categories else None,
            cover_url=cover_url(b.cover_path), shelf_count=shelves,
        )
        for b, shelves in entries
    ]


@router.put("/books/{book_id}/public", response_model=AdminBookResponse)
def set_book_public(book_id: int, req: PublicRequest, admin: User = Depends(require_admin)) -> AdminBookResponse:
    """Publish the admin's own book, or take a public book back to private. Anyone else's private book looks missing."""
    engine = get_db_engine()
    repo = SqlBookRepository(engine)
    book = repo.get_by_id(book_id)
    if book is None or not (book.is_public or book.owner_id == admin.id):
        raise HTTPException(404, f"Book {book_id} not found")
    repo.set_public(book_id, req.is_public)
    return next(b for b in list_system_books(admin) if b.id == book_id)


# ------------------------------------------------------------------------------------------ categories

def _category_response(engine: Engine, category_id: int) -> CategoryAdminResponse:
    repo = SqlCategoryRepository(engine)
    category = repo.get(category_id)
    assert category is not None
    return CategoryAdminResponse(**category, book_count=repo.book_counts().get(category_id, 0))


@router.get("/categories", response_model=list[CategoryAdminResponse])
def list_categories_admin() -> list[CategoryAdminResponse]:
    repo = SqlCategoryRepository(get_db_engine())
    counts = repo.book_counts()
    return [CategoryAdminResponse(**c, book_count=counts.get(c["id"], 0)) for c in repo.list_all()]


def _check_name_free(repo: SqlCategoryRepository, name: str, own_id: int | None = None) -> None:
    """Names are unique ignoring case and accents ("Lịch sử" and "lich su" are the same tag)."""
    wanted = _slug(name)
    if any(_slug(c["name"]) == wanted and c["id"] != own_id for c in repo.list_all()):
        raise HTTPException(409, f"A category named '{name}' already exists.")


@router.post("/categories", status_code=201, response_model=CategoryAdminResponse)
def create_category(req: CategoryRequest) -> CategoryAdminResponse:
    engine = get_db_engine()
    repo = SqlCategoryRepository(engine)
    _check_name_free(repo, req.name)
    taken = {c["slug"] for c in repo.list_all()}
    base = slug = _slug(req.name)
    number = 2
    while slug in taken:  # two categories may not share a slug: "Kỹ năng" and "Ky nang" become ky-nang, ky-nang-2
        slug, number = f"{base}-{number}", number + 1
    new_id = repo.create(req.name, slug, req.icon, req.color)
    return _category_response(engine, new_id)


@router.put("/categories/{category_id}", response_model=CategoryAdminResponse)
def update_category(category_id: int, req: CategoryRequest) -> CategoryAdminResponse:
    engine = get_db_engine()
    repo = SqlCategoryRepository(engine)
    if repo.get(category_id) is None:
        raise HTTPException(404, f"Category {category_id} not found")
    _check_name_free(repo, req.name, category_id)
    repo.update(category_id, req.name, req.icon, req.color)
    return _category_response(engine, category_id)


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: int) -> None:
    repo = SqlCategoryRepository(get_db_engine())
    category = repo.get(category_id)
    if category is None:
        raise HTTPException(404, f"Category {category_id} not found")
    if category["slug"] == PROTECTED_SLUG:
        raise HTTPException(400, "The category 'Khác' cannot be deleted.")
    repo.delete(category_id)


# ---------------------------------------------------------------------------------------------- voices

def _voice(v: dict[str, Any], admin: User) -> VoiceResponse:
    return VoiceResponse(
        voice_id=v["voice_id"], display_name=v["display_name"], provider=v["provider"], language=v["language"],
        gender=v["gender"], style=v["style"], is_custom=True, consent_at=v["consent_at"],
        is_public=v["is_public"], is_mine=v["owner_id"] == admin.id,
    )


@router.get("/voices", response_model=AdminVoicesResponse)
def list_system_voices(admin: User = Depends(require_admin)) -> AdminVoicesResponse:
    """Public voices and the admin's own clones. Other people's private clones are not listed."""
    engine = get_db_engine()
    voices = SqlVoiceRepository(engine).list_voices(admin.id)
    return AdminVoicesResponse(
        voices=[_voice(v, admin) for v in voices],
        default_voice=SqlSettingsRepository(engine).get("system_default_voice") or "",
    )


@router.put("/voices/{voice_id}/public", response_model=VoiceResponse)
def set_voice_public(voice_id: str, req: PublicRequest, admin: User = Depends(require_admin)) -> VoiceResponse:
    repo = SqlVoiceRepository(get_db_engine())
    voice = repo.get_voice(voice_id)
    if voice is None or not (voice["is_public"] or voice["owner_id"] == admin.id):
        raise HTTPException(404, f"Voice '{voice_id}' not found")
    repo.set_public(voice_id, req.is_public)
    return _voice({**voice, "is_public": req.is_public}, admin)


@router.put("/default-voice", response_model=AdminVoicesResponse)
def set_default_voice(req: DefaultVoiceRequest, admin: User = Depends(require_admin)) -> AdminVoicesResponse:
    """The voice everyone starts with (unless they chose their own). Must be a provider voice or a public/own clone."""
    engine = get_db_engine()
    voice = SqlVoiceRepository(engine).get_voice(req.voice_id)
    if voice is not None:
        if not (voice["is_public"] or voice["owner_id"] == admin.id):
            raise HTTPException(404, f"Voice '{req.voice_id}' not found")
        if not voice["is_public"]:
            raise HTTPException(400, "Publish the voice first: a private voice cannot be the system default.")
    else:
        try:
            known = {v.voice_id for v in TTSFactory.create_provider().list_voices()}
        except TTSProviderError:
            known = set()
        if req.voice_id not in known:
            raise HTTPException(404, f"Voice '{req.voice_id}' not found")
    SqlSettingsRepository(engine).set("system_default_voice", req.voice_id)
    return list_system_voices(admin)


# ---------------------------------------------------------------------------------------------- users

@router.get("/users", response_model=list[AdminUserResponse])
def list_users() -> list[AdminUserResponse]:
    """Accounts only (read-only): name, role, date and how many books/voices they own — never their content."""
    engine = get_db_engine()
    with engine.connect() as conn:
        books = {int(r[0]): int(r[1]) for r in conn.execute(
            text("SELECT owner_id, COUNT(*) FROM books WHERE owner_id IS NOT NULL GROUP BY owner_id"))}
        voices = {int(r[0]): int(r[1]) for r in conn.execute(
            text("SELECT owner_id, COUNT(*) FROM voice_profiles WHERE owner_id IS NOT NULL GROUP BY owner_id"))}
    return [
        AdminUserResponse(
            id=u.id, username=u.username, full_name=u.full_name, role=u.role, created_at=created,
            book_count=books.get(u.id, 0), voice_count=voices.get(u.id, 0),
        )
        for u, created in SqlUserRepository(engine).list_all()
    ]


# ------------------------------------------------------------------------------------------ background sounds

@router.post("/ambient", status_code=201, response_model=AmbientTrackResponse)
def add_ambient(name: str = Form(..., min_length=1, max_length=100), file: UploadFile = File(...)) -> AmbientTrackResponse:
    """Add a sound to the library (mp3/ogg/wav/m4a, up to 15 MB). Everyone may then choose it in the player."""
    data = file.file.read(MAX_AMBIENT_BYTES + 1)
    try:
        stored, size = save_ambient(file.filename or "", data)
    except AmbientError as exc:
        raise HTTPException(400, str(exc)) from exc
    repo = SqlAmbientRepository(get_db_engine())
    track = repo.get(repo.add(" ".join(name.split()) or "Âm thanh nền", stored, size))
    assert track is not None
    return track_response(track)


@router.patch("/ambient/{track_id}", response_model=AmbientTrackResponse)
def rename_ambient(track_id: int, req: AmbientRenameRequest) -> AmbientTrackResponse:
    repo = SqlAmbientRepository(get_db_engine())
    if not repo.rename(track_id, req.name):
        raise HTTPException(404, f"Sound {track_id} not found")
    track = repo.get(track_id)
    assert track is not None
    return track_response(track)


@router.delete("/ambient/{track_id}", status_code=204)
def delete_ambient(track_id: int) -> None:
    """Remove a sound. People who had chosen it simply hear nothing until they pick another."""
    repo = SqlAmbientRepository(get_db_engine())
    track = repo.get(track_id)
    if track is None:
        raise HTTPException(404, f"Sound {track_id} not found")
    repo.delete(track_id)
    delete_ambient_file(track["file_name"])
