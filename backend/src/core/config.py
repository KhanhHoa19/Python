"""Centralized application configuration loader using python-dotenv and Pydantic."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env file at startup
load_dotenv()


class Settings(BaseModel):
    """Application settings with defaults from environment variables."""

    # Database settings
    db_host: str = Field(default_factory=lambda: os.getenv("DB_HOST", "127.0.0.1"))
    db_port: int = Field(default_factory=lambda: int(os.getenv("DB_PORT", "3306")))
    db_user: str = Field(default_factory=lambda: os.getenv("DB_USER", "root"))
    db_password: str = Field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))
    db_name: str = Field(default_factory=lambda: os.getenv("DB_NAME", "studylab_audiobook"))

    # SQLite fallback (enabled via DB_USE_SQLITE=true or when DB_HOST is empty)
    db_use_sqlite: bool = Field(
        default_factory=lambda: os.getenv("DB_USE_SQLITE", "false").lower() in ("true", "1", "yes")
    )
    sqlite_path: str = Field(default_factory=lambda: os.getenv("SQLITE_PATH", ".studylab/studylab.db"))

    # Speech synthesis settings
    tts_provider: str = Field(default_factory=lambda: os.getenv("TTS_PROVIDER", "edge-tts"))
    tts_default_voice: str = Field(
        default_factory=lambda: os.getenv("TTS_DEFAULT_VOICE", "en-US-ChristopherNeural")
    )
    openai_api_key: str | None = Field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY") or None
    )

    # HeyGen Voice (used when TTS_PROVIDER=heygen)
    heygen_api_key: str | None = Field(default_factory=lambda: os.getenv("HEYGEN_API_KEY") or None)
    heygen_model: str = Field(default_factory=lambda: os.getenv("HEYGEN_MODEL", "heygen-voice-1"))
    heygen_language: str = Field(default_factory=lambda: os.getenv("HEYGEN_LANGUAGE", "vi"))
    heygen_audio_format: str = Field(default_factory=lambda: os.getenv("HEYGEN_AUDIO_FORMAT", "mp3"))
    heygen_default_voice: str | None = Field(default_factory=lambda: os.getenv("HEYGEN_DEFAULT_VOICE") or None)
    # HeyGen allows 30 requests/minute per workspace member; stay just below it.
    heygen_requests_per_minute: int = Field(
        default_factory=lambda: int(os.getenv("HEYGEN_REQUESTS_PER_MINUTE", "28"))
    )

    # Mock provider knobs (TTS_PROVIDER=mock): simulated latency and failure rate for testing the player
    mock_latency_seconds: float = Field(default_factory=lambda: float(os.getenv("MOCK_TTS_LATENCY_SECONDS", "0")))
    mock_jitter_seconds: float = Field(default_factory=lambda: float(os.getenv("MOCK_TTS_JITTER_SECONDS", "0")))
    mock_error_rate: float = Field(default_factory=lambda: float(os.getenv("MOCK_TTS_ERROR_RATE", "0")))
    mock_seed: int | None = Field(
        default_factory=lambda: int(os.environ["MOCK_TTS_SEED"]) if os.getenv("MOCK_TTS_SEED") else None
    )

    # Telemetry and ping probe targets
    lan_ping_host: str = Field(default_factory=lambda: os.getenv("LAN_PING_HOST", "192.168.1.1"))
    tailscale_ping_host: str = Field(
        default_factory=lambda: os.getenv("TAILSCALE_PING_HOST", "100.100.100.100")
    )

    # Accounts. JWT_SECRET empty = a random secret is kept in the database.
    jwt_secret: str = Field(default_factory=lambda: os.getenv("JWT_SECRET", ""))
    jwt_expire_hours: float = Field(default_factory=lambda: float(os.getenv("JWT_EXPIRE_HOURS", "12")))
    admin_username: str = Field(default_factory=lambda: os.getenv("ADMIN_USERNAME", "admin"))
    admin_password: str = Field(default_factory=lambda: os.getenv("ADMIN_PASSWORD", ""))
    # DEVELOPMENT ONLY: show three ready-made accounts as one-click boxes on the sign-in page. They carry
    # their passwords in the clear, so this must stay off anywhere other people can reach the app.
    dev_quick_login: bool = Field(default_factory=lambda: os.getenv("DEV_QUICK_LOGIN", "false").lower() in ("1", "true", "yes"))
    max_voices_per_user: int = Field(default_factory=lambda: int(os.getenv("MAX_VOICES_PER_USER", "3")))

    # Local audio cache directory
    audio_cache_dir: str = Field(
        default_factory=lambda: os.getenv("AUDIO_CACHE_DIR", ".studylab/cache/audio")
    )

    # Voice samples (cloning) and exported audio
    voice_samples_dir: str = Field(
        default_factory=lambda: os.getenv("VOICE_SAMPLES_DIR", ".studylab/voice_samples")
    )
    cover_dir: str = Field(default_factory=lambda: os.getenv("COVER_DIR", ".studylab/covers"))
    ambient_dir: str = Field(default_factory=lambda: os.getenv("AMBIENT_DIR", ".studylab/ambient"))
    quotes_dir: str = Field(default_factory=lambda: os.getenv("QUOTES_DIR", ".studylab/quotes"))
    export_dir: str = Field(default_factory=lambda: os.getenv("EXPORT_DIR", ".studylab/exports"))

    @property
    def effective_default_voice(self) -> str:
        """Default voice of the active provider (a HeyGen voice id is not an Edge/OpenAI voice name)."""
        if self.tts_provider.lower() == "heygen" and self.heygen_default_voice:
            return self.heygen_default_voice
        return self.tts_default_voice

    def get_database_url(self) -> str:
        """Construct database connection string."""
        if self.db_use_sqlite or not self.db_host:
            # Ensure parent directory for SQLite file exists
            path = Path(self.sqlite_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{self.sqlite_path}"

        # Standard MySQL connection via PyMySQL driver
        pw_part = f":{self.db_password}" if self.db_password else ""
        return (
            f"mysql+pymysql://{self.db_user}{pw_part}@{self.db_host}:{self.db_port}/"
            f"{self.db_name}?charset=utf8mb4"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
