"""Pydantic validation schemas for Telemetry and Analytics."""

from __future__ import annotations

from pydantic import BaseModel


class AnalyticsSummaryResponse(BaseModel):
    total_listening_minutes: float
    total_words_absorbed: int
    total_sessions: int
    avg_sentence_response_time_sec: float
    avg_lan_ping_ms: float
    avg_tailscale_ping_ms: float
    recent_sessions_count: int


class DailyStat(BaseModel):
    date: str
    minutes: float
    words: int
    sessions: int


class VoiceStat(BaseModel):
    voice: str  # empty when the session was recorded without a voice
    display_name: str
    minutes: float
    words: int
    sessions: int


class MetricsResponse(BaseModel):
    total_calls: int
    avg_latency_ms: float
    p95_latency_ms: float
    max_latency_ms: float
    success_rate: float
    words_per_minute: float
