"""Desktop app configuration, read from environment variables (optionally a .env file)."""

from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv() -> None:
    """Load KEY=VALUE pairs from the repo-level .env without overriding real environment."""
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if not candidate.is_file():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())
        return


_load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("API_TIMEOUT_SECONDS", "30"))
# Synthesizing a sentence can be slow on a cold cache, so audio requests get a longer timeout.
AUDIO_TIMEOUT_SECONDS = float(os.getenv("API_AUDIO_TIMEOUT_SECONDS", "60"))
SPEED_LEVELS = (0.75, 1.0, 1.25, 1.5)
BOOKMARK_SAVE_INTERVAL_SECONDS = 5.0
