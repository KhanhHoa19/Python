"""Typed application settings stored in the database, with validation and defaults."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from src.core.config import get_settings
from src.core.storage.repositories import SqlSettingsRepository, SqlUserSettingsRepository


@dataclass
class AppSettings:
    prefetch_count: int = 2
    default_speed: float = 1.0
    default_voice: str = ""
    daily_char_limit: int = 0  # 0 = unlimited
    ambient_track: int = 0  # id of the background sound (0 = none)
    ambient_volume: float = 0.4
    chapter_chime: bool = True  # a short chime when playback moves on to the next chapter
    character_voice: str = ""  # voice of the dialogue in quotation marks (multi-voice narration); "" = one voice

    def validate(self) -> None:
        if not 1 <= self.prefetch_count <= 5:
            raise ValueError("prefetch_count must be between 1 and 5")
        if not 0.5 <= self.default_speed <= 3.0:
            raise ValueError("default_speed must be between 0.5 and 3.0")
        if self.daily_char_limit < 0:
            raise ValueError("daily_char_limit must be >= 0")
        if self.ambient_track < 0:
            raise ValueError("ambient_track must be >= 0")
        if not 0.0 <= self.ambient_volume <= 1.0:
            raise ValueError("ambient_volume must be between 0 and 1")
        if not self.default_voice.strip():
            raise ValueError("default_voice must not be empty")

    def as_dict(self) -> dict[str, int | float | str]:
        return asdict(self)


# Per person: how they listen. System-wide (admin only): the daily character limit, which protects the TTS bill.
USER_KEYS = ("prefetch_count", "default_speed", "default_voice", "ambient_track", "ambient_volume", "chapter_chime", "character_voice")


def load_app_settings(repo: SqlSettingsRepository, user_repo: SqlUserSettingsRepository) -> AppSettings:
    """The user's preferences with the system-wide limit, falling back to defaults."""
    # An admin may pick the system default voice; it replaces the one from .env for everyone who chose none.
    defaults = AppSettings(default_voice=repo.get("system_default_voice") or get_settings().effective_default_voice)
    return AppSettings(
        prefetch_count=int(user_repo.get("prefetch_count", str(defaults.prefetch_count)) or defaults.prefetch_count),
        default_speed=float(user_repo.get("default_speed", str(defaults.default_speed)) or defaults.default_speed),
        default_voice=user_repo.get("default_voice", defaults.default_voice) or defaults.default_voice,
        daily_char_limit=int(repo.get("daily_char_limit", str(defaults.daily_char_limit)) or 0),
        ambient_track=int(user_repo.get("ambient_track", "0") or 0),
        ambient_volume=float(user_repo.get("ambient_volume", str(defaults.ambient_volume)) or defaults.ambient_volume),
        chapter_chime=(user_repo.get("chapter_chime", "True") or "True") == "True",
        character_voice=user_repo.get("character_voice", "") or "",
    )


def save_app_settings(
    repo: SqlSettingsRepository, user_repo: SqlUserSettingsRepository, new: AppSettings, can_set_limit: bool
) -> None:
    """Save the user's preferences; the system-wide limit only changes if `can_set_limit` (admin)."""
    new.validate()
    for key in USER_KEYS:
        user_repo.set(key, str(getattr(new, key)))
    if can_set_limit:
        repo.set("daily_char_limit", str(new.daily_char_limit))
