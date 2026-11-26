"""Typed application settings stored in the database, with validation and defaults."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from src.core.config import get_settings
from src.core.storage.repositories import SqlSettingsRepository


@dataclass
class AppSettings:
    prefetch_count: int = 2
    default_speed: float = 1.0
    default_voice: str = ""
    daily_char_limit: int = 0  # 0 = unlimited

    def validate(self) -> None:
        if not 1 <= self.prefetch_count <= 5:
            raise ValueError("prefetch_count must be between 1 and 5")
        if not 0.5 <= self.default_speed <= 3.0:
            raise ValueError("default_speed must be between 0.5 and 3.0")
        if self.daily_char_limit < 0:
            raise ValueError("daily_char_limit must be >= 0")
        if not self.default_voice.strip():
            raise ValueError("default_voice must not be empty")

    def as_dict(self) -> dict[str, int | float | str]:
        return asdict(self)


def load_app_settings(repo: SqlSettingsRepository) -> AppSettings:
    """Load settings from DB, falling back to defaults (default voice from environment config)."""
    defaults = AppSettings(default_voice=get_settings().tts_default_voice)
    return AppSettings(
        prefetch_count=int(repo.get("prefetch_count", str(defaults.prefetch_count)) or defaults.prefetch_count),
        default_speed=float(repo.get("default_speed", str(defaults.default_speed)) or defaults.default_speed),
        default_voice=repo.get("default_voice", defaults.default_voice) or defaults.default_voice,
        daily_char_limit=int(repo.get("daily_char_limit", str(defaults.daily_char_limit)) or 0),
    )


def save_app_settings(repo: SqlSettingsRepository, new: AppSettings) -> None:
    new.validate()
    for key, value in new.as_dict().items():
        repo.set(key, str(value))
