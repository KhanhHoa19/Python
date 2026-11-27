"""Files of the background-sound library: where they live, what is accepted, how they are served."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from src.core.config import get_settings

ALLOWED_EXTENSIONS = {".mp3", ".ogg", ".wav", ".m4a"}
MEDIA_TYPES = {".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".wav": "audio/wav", ".m4a": "audio/mp4"}
MAX_AMBIENT_BYTES = 15 * 1024 * 1024
FILE_NAME = re.compile(r"^[0-9a-f]{32}\.(mp3|ogg|wav|m4a)$")


class AmbientError(ValueError):
    """The uploaded file cannot be used as a background sound."""


def ambient_dir() -> Path:
    path = Path(get_settings().ambient_dir).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def looks_like_audio(extension: str, data: bytes) -> bool:
    """Cheap check of the file's first bytes, so a renamed document is not stored as music."""
    head = data[:12]
    if extension == ".mp3":
        return head[:3] == b"ID3" or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0)
    if extension == ".wav":
        return head[:4] == b"RIFF" and head[8:12] == b"WAVE"
    if extension == ".ogg":
        return head[:4] == b"OggS"
    if extension == ".m4a":
        return head[4:8] == b"ftyp"
    return False


def save_ambient(filename: str, data: bytes) -> tuple[str, int]:
    """Store an uploaded sound under a random name. Returns (stored name, size). Raises AmbientError."""
    extension = Path(filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise AmbientError(f"Unsupported format. Use: {', '.join(sorted(ALLOWED_EXTENSIONS))}.")
    if not data:
        raise AmbientError("The file is empty.")
    if len(data) > MAX_AMBIENT_BYTES:
        raise AmbientError(f"The file exceeds {MAX_AMBIENT_BYTES // (1024 * 1024)} MB.")
    if not looks_like_audio(extension, data):
        raise AmbientError("The file is not valid audio.")
    name = f"{uuid.uuid4().hex}{extension}"
    (ambient_dir() / name).write_bytes(data)
    return name, len(data)


def ambient_path(name: str) -> Path | None:
    """The stored file, or None. The name is checked against a strict pattern first (no path traversal)."""
    if not FILE_NAME.match(name):
        return None
    path = ambient_dir() / name
    return path if path.is_file() else None


def delete_ambient_file(name: str) -> None:
    path = ambient_path(name)
    if path:
        path.unlink(missing_ok=True)
