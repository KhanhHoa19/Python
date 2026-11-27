"""Settings API router: each user's reading preferences, and the system-wide daily character limit."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine

from src.api.deps import check_voice_access, current_user
from src.api.schemas.settings_schemas import SettingsResponse, SettingsUpdateRequest
from src.core.app_settings import AppSettings, load_app_settings, save_app_settings
from src.core.auth.users import User
from src.core.storage.db import get_db_engine
from src.core.storage.repositories import (
    SqlAmbientRepository,
    SqlSettingsRepository,
    SqlUserSettingsRepository,
)
from src.core.tts.factory import TTSFactory

router = APIRouter(tags=["settings"])


def _response(engine: Engine, user: User) -> SettingsResponse:
    repo = SqlSettingsRepository(engine)
    current = load_app_settings(repo, SqlUserSettingsRepository(engine, user.id))
    return SettingsResponse(
        prefetch_count=current.prefetch_count,
        default_speed=current.default_speed,
        default_voice=current.default_voice,
        daily_char_limit=current.daily_char_limit,
        # A sound an admin deleted counts as "none" (the choice itself is cleared the next time the user saves).
        ambient_track=current.ambient_track if SqlAmbientRepository(engine).get(current.ambient_track) else 0,
        ambient_volume=current.ambient_volume,
        chapter_chime=current.chapter_chime,
        character_voice=current.character_voice,
        chars_used_today=repo.chars_used_today(),
        provider=TTSFactory.create_provider().provider_name,
    )


@router.get("", response_model=SettingsResponse)
def get_app_settings(user: User = Depends(current_user)) -> SettingsResponse:
    return _response(get_db_engine(), user)


@router.put("", response_model=SettingsResponse)
def update_app_settings(req: SettingsUpdateRequest, user: User = Depends(current_user)) -> SettingsResponse:
    """Saves the caller's own preferences. `daily_char_limit` is shared by everyone and only an admin can change it."""
    engine = get_db_engine()
    repo, user_repo = SqlSettingsRepository(engine), SqlUserSettingsRepository(engine, user.id)
    new = AppSettings(**{**load_app_settings(repo, user_repo).as_dict(), **req.model_dump(exclude_none=True)})
    if new.ambient_track and SqlAmbientRepository(engine).get(new.ambient_track) is None:
        raise HTTPException(400, f"Unknown background sound {new.ambient_track}")
    check_voice_access(engine, new.character_voice, user)  # someone else's private clone looks like a missing voice
    save_app_settings(repo, user_repo, new, can_set_limit=user.is_admin)
    return _response(engine, user)
