"""Integration tests for Analytics API and headless Matplotlib chart streams."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from src.api.app import create_app
from tests.auth_helpers import sign_in, tester, use_engine


@pytest.fixture
def app_client(test_engine: Engine) -> Generator[TestClient, None, None]:
    """Create FastAPI test client with in-memory database engine."""
    with use_engine(test_engine):
        app = create_app()
        with TestClient(app) as client:
            yield sign_in(client, test_engine, tester(test_engine))


def test_get_analytics_summary(app_client: TestClient) -> None:
    """Test fetching analytics summary JSON."""
    resp = app_client.get("/api/analytics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_listening_minutes" in data
    assert "total_words_absorbed" in data
    assert "avg_sentence_response_time_sec" in data
    assert "avg_lan_ping_ms" in data
    assert "avg_tailscale_ping_ms" in data


def test_get_listening_trends_chart_png(app_client: TestClient) -> None:
    """Test streaming headless Matplotlib listening trends PNG chart."""
    resp = app_client.get("/api/analytics/charts/listening-trends.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content.startswith(b"\x89PNG")  # Standard PNG magic bytes


def test_get_latency_metrics_chart_png(app_client: TestClient) -> None:
    """Test streaming headless Matplotlib latency overview PNG chart."""
    resp = app_client.get("/api/analytics/charts/latency-metrics.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content.startswith(b"\x89PNG")  # Standard PNG magic bytes
