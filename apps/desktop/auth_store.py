"""The saved sign-in of the desktop app: one small file in the user's config folder, readable only by them."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _file() -> Path:
    base = os.getenv("AUDIOBOOK_TTS_CONFIG_DIR")
    return (Path(base) if base else Path.home() / ".config" / "audiobook-tts") / "session.json"


def load() -> dict[str, Any] | None:
    """{"token": ..., "user": {...}} or None if nothing usable is saved."""
    try:
        data = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    user = data.get("user")
    if not isinstance(data.get("token"), str) or not data["token"] or not isinstance(user, dict):
        return None
    return {"token": data["token"], "user": user}


def save(token: str, user: dict[str, Any]) -> None:
    """Write the file with mode 600 from the start (never briefly readable by others)."""
    path = _file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"token": token, "user": user}, handle)
        os.chmod(path, 0o600)  # also tightens a file that already existed with wider rights
    except OSError:
        pass  # the sign-in then lasts until the app is closed


def clear() -> None:
    try:
        _file().unlink()
    except OSError:
        pass
