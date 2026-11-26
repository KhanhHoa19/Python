"""Analytics API router: aggregated KPI metrics and headless Matplotlib PNG charts."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response

from src.api.schemas.analytics_schemas import AnalyticsSummaryResponse, DailyStat, MetricsResponse
from src.core.analytics.dashboard import (
    generate_latency_metrics_chart,
    generate_listening_trends_chart,
)
from src.core.storage.db import get_db_engine
from src.core.storage.repositories import SqlSessionRepository, SqlTelemetryRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analytics"])

_NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}


@router.get("/summary", response_model=AnalyticsSummaryResponse)
def get_analytics_summary(days: int = 7, book_id: int | None = None) -> AnalyticsSummaryResponse:
    """Retrieve aggregated reading session and network latency metrics."""
    engine = get_db_engine()
    telemetry_repo = SqlTelemetryRepository(engine)
    session_repo = SqlSessionRepository(engine)

    metrics = telemetry_repo.get_aggregated_metrics(book_id=book_id, days=days)
    recent_sessions = session_repo.get_recent_sessions(book_id=book_id, days=days)

    return AnalyticsSummaryResponse(
        total_listening_minutes=metrics.get("total_listening_minutes", 0.0),
        total_words_absorbed=metrics.get("total_words_absorbed", 0),
        total_sessions=metrics.get("total_sessions", 0),
        avg_sentence_response_time_sec=metrics.get("avg_sentence_response_time_sec", 0.0),
        avg_lan_ping_ms=metrics.get("avg_lan_ping_ms", 0.0),
        avg_tailscale_ping_ms=metrics.get("avg_tailscale_ping_ms", 0.0),
        recent_sessions_count=len(recent_sessions),
    )


@router.get("/charts/listening-trends.png")
def get_listening_trends_chart(days: int = 7) -> Response:
    """Return headless Matplotlib PNG chart of daily listening habits."""
    session_repo = SqlSessionRepository(get_db_engine())
    chart_bytes = generate_listening_trends_chart(session_repo, days=days)
    return Response(chart_bytes, media_type="image/png", headers=_NO_CACHE)


@router.get("/charts/latency-metrics.png")
def get_latency_metrics_chart(days: int = 7) -> Response:
    """Return headless Matplotlib PNG chart of network ping and TTS latency."""
    telemetry_repo = SqlTelemetryRepository(get_db_engine())
    chart_bytes = generate_latency_metrics_chart(telemetry_repo, days=days)
    return Response(chart_bytes, media_type="image/png", headers=_NO_CACHE)


@router.get("/daily", response_model=list[DailyStat])
def get_daily_stats(days: int = 7) -> list[DailyStat]:
    """Minutes, words and sessions per calendar day (zero-filled), for bar charts."""
    days = min(max(days, 1), 365)
    return [DailyStat(**row) for row in SqlSessionRepository(get_db_engine()).get_daily_stats(days)]


@router.get("/metrics", response_model=MetricsResponse)
def get_metrics(days: int = 7) -> MetricsResponse:
    """Latency (avg/P95/max), API success rate and average reading speed."""
    days = min(max(days, 1), 365)
    engine = get_db_engine()
    latency = SqlTelemetryRepository(engine).get_latency_stats(days)
    daily = SqlSessionRepository(engine).get_daily_stats(days)
    minutes = sum(d["minutes"] for d in daily)
    words = sum(d["words"] for d in daily)
    return MetricsResponse(**latency, words_per_minute=round(words / minutes, 1) if minutes else 0.0)
