"""The audio of a favourite quote is copied out of the cache, so clearing the cache never loses it."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from src.core.config import get_settings

# The feelings a quote can be tagged with: slug -> label shown to the user.
EMOTION_TAGS = {
    "inspiring": "Truyền cảm hứng",
    "touching": "Chạm cảm xúc",
    "wise": "Triết lý hay",
    "funny": "Hài hước",
}


def quotes_root() -> Path:
    path = Path(get_settings().quotes_dir).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_quote_audio(source: Path, user_id: int) -> str:
    """Copy `source` to <quotes>/<user_id>/<random>.<ext> and return that path relative to the quotes folder."""
    folder = quotes_root() / str(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{source.suffix.lower()}"
    shutil.copyfile(source, folder / name)
    return f"{user_id}/{name}"


def quote_audio_path(relative: str | None) -> Path | None:
    """The stored file, or None if there is none, it is gone, or the stored value tries to leave the quotes folder."""
    if not relative:
        return None
    root = quotes_root()
    path = (root / relative).resolve()
    return path if path.is_relative_to(root) and path.is_file() else None


def delete_quote_audio(relative: str | None) -> None:
    path = quote_audio_path(relative)
    if path is not None:
        path.unlink(missing_ok=True)
