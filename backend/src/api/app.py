"""FastAPI application factory and HTTP server configuration."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.core.player.audio_service import QuotaExceededError

logger = logging.getLogger(__name__)


def create_app(test_config: dict[str, Any] | None = None) -> FastAPI:
    """Initialize and configure the FastAPI REST API application."""
    app = FastAPI(title="Audiobook TTS API", version="0.1.0")
    app.state.config = dict(test_config or {})

    # Configure CORS for frontend access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Error handlers keep the legacy {"error": ...} response shape.
    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, err: StarletteHTTPException) -> JSONResponse:
        return JSONResponse({"error": str(err.detail)}, status_code=err.status_code)

    @app.exception_handler(RequestValidationError)
    @app.exception_handler(ValidationError)
    async def handle_validation_error(_: Request, err: Exception) -> JSONResponse:
        logger.warning(f"Request validation failed: {err}")
        details = err.errors()  # type: ignore[attr-defined]
        return JSONResponse(
            {"error": "Validation error", "details": jsonable(details)}, status_code=400
        )

    @app.exception_handler(FileNotFoundError)
    @app.exception_handler(LookupError)
    async def handle_not_found_error(_: Request, err: Exception) -> JSONResponse:
        logger.warning(f"Resource not found: {err}")
        return JSONResponse({"error": str(err)}, status_code=404)

    @app.exception_handler(ValueError)
    async def handle_value_error(_: Request, err: ValueError) -> JSONResponse:
        logger.warning(f"Unprocessable entity: {err}")
        return JSONResponse({"error": str(err)}, status_code=422)

    @app.exception_handler(QuotaExceededError)
    async def handle_quota_error(_: Request, err: QuotaExceededError) -> JSONResponse:
        return JSONResponse({"error": str(err)}, status_code=429)

    @app.exception_handler(Exception)
    async def handle_generic_exception(_: Request, err: Exception) -> JSONResponse:
        logger.error(f"Internal server error: {err}", exc_info=True)
        return JSONResponse({"error": "Internal server error"}, status_code=500)

    @app.get("/api/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok", "version": "0.1.0"}

    from src.api.routes.analytics import router as analytics_router
    from src.api.routes.books import router as books_router
    from src.api.routes.export import router as export_router
    from src.api.routes.health import router as health_router
    from src.api.routes.notes import router as notes_router
    from src.api.routes.player import router as player_router
    from src.api.routes.settings import router as settings_router
    from src.api.routes.voices import router as voices_router

    app.include_router(books_router, prefix="/api/books")
    app.include_router(player_router, prefix="/api")
    app.include_router(analytics_router, prefix="/api/analytics")
    app.include_router(voices_router, prefix="/api/voices")
    app.include_router(notes_router, prefix="/api/notes")
    app.include_router(settings_router, prefix="/api/settings")
    app.include_router(health_router, prefix="/api")
    app.include_router(export_router, prefix="/api")

    return app


def jsonable(value: Any) -> Any:
    """Make pydantic error details JSON-serializable."""
    from fastapi.encoders import jsonable_encoder

    return jsonable_encoder(value, custom_encoder={Exception: str})


app = create_app()

if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run("src.api.app:app", host="0.0.0.0", port=5000, reload=True)
