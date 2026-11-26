"""Settings API router: reading preferences and daily character limit."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.schemas.settings_schemas import SettingsResponse, SettingsUpdateRequest
from src.core.app_settings import AppSettings, load_app_settings, save_app_settings
from src.core.storage.db import get_db_engine
from src.core.storage.repositories import SqlSettingsRepository
from src.core.tts.factory import TTSFactory

router = APIRouter(tags=["settings"])


def _response(repo: SqlSettingsRepository) -> SettingsResponse:
    current = load_app_settings(repo)
    return SettingsResponse(
        prefetch_count=current.prefetch_count,
        default_speed=current.default_speed,
        default_voice=current.default_voice,
        daily_char_limit=current.daily_char_limit,
        chars_used_today=repo.chars_used_today(),
        provider=TTSFactory.create_provider().provider_name,
    )


@router.get("", response_model=SettingsResponse)
def get_app_settings() -> SettingsResponse:
    return _response(SqlSettingsRepository(get_db_engine()))


@router.put("", response_model=SettingsResponse)
def update_app_settings(req: SettingsUpdateRequest) -> SettingsResponse:
    repo = SqlSettingsRepository(get_db_engine())
    save_app_settings(repo, AppSettings(**req.model_dump()))
    return _response(repo)
