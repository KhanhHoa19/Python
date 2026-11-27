"""Background sounds: the list for every signed-in user, and the audio files (public, like covers: <audio> sends no token)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.api.schemas.ambient_schemas import AmbientTrackResponse
from src.core.audio.ambient import MEDIA_TYPES, ambient_path
from src.core.storage.db import get_db_engine
from src.core.storage.repositories import SqlAmbientRepository

router = APIRouter(tags=["ambient"])  # mounted behind sign-in
public_router = APIRouter(tags=["ambient"])  # mounted without it


def track_response(track: dict[str, Any]) -> AmbientTrackResponse:
    return AmbientTrackResponse(
        id=track["id"], name=track["name"], url=f"/api/ambient/{track['id']}/audio", size_bytes=track["size_bytes"])


@router.get("", response_model=list[AmbientTrackResponse])
def list_ambient() -> list[AmbientTrackResponse]:
    return [track_response(t) for t in SqlAmbientRepository(get_db_engine()).list_all()]


@public_router.get("/ambient/{track_id}/audio")
def get_ambient_audio(track_id: int) -> FileResponse:
    track = SqlAmbientRepository(get_db_engine()).get(track_id)
    path = ambient_path(track["file_name"]) if track else None
    if path is None:
        raise HTTPException(404, "Sound not found")
    return FileResponse(path, media_type=MEDIA_TYPES.get(path.suffix, "audio/mpeg"),
                        headers={"Cache-Control": "public, max-age=86400"})
