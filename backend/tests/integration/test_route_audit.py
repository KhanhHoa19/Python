"""Audit of EVERY endpoint, generated from the OpenAPI document, so a new route cannot slip in unprotected.

- Only the routes listed in PUBLIC may be reached without signing in.
- Every other route answers 401 to an anonymous caller, whatever its parameters.
- Administrator-only routes answer 403 to an ordinary member."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from src.api.app import create_app
from tests.auth_helpers import make_user, sign_in
from tests.integration.test_accounts import app  # noqa: F401  (fixture)
from tests.integration.test_api_extended import provider  # noqa: F401

# Public on purpose: sign-in itself, health for the load balancer, and files an <img>/<audio> tag fetches without a token
# (covers have random names; ambient sounds are music for everyone).
PUBLIC = {
    ("GET", "/api/health"), ("POST", "/api/auth/login"), ("POST", "/api/auth/register"),
    ("GET", "/api/auth/demo-accounts"), ("GET", "/api/covers/{name}"), ("GET", "/api/ambient/{track_id}/audio"),
}
# Administrators only, beyond everything under /api/admin.
ADMIN_ONLY_EXTRA = {("GET", "/api/health/network"), ("POST", "/api/tts/verify")}


def _operations() -> list[tuple[str, str, bool]]:
    spec = create_app().openapi()
    return [
        (method.upper(), path, bool(op.get("security")))
        for path, item in spec["paths"].items() for method, op in item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]


def _url(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", path)


def test_only_the_expected_routes_are_public() -> None:
    open_routes = {(m, p) for m, p, secured in _operations() if not secured}
    assert open_routes == PUBLIC, f"unexpected public routes: {open_routes ^ PUBLIC}"


@pytest.mark.parametrize(("method", "path"), [(m, p) for m, p, secured in _operations() if secured])
def test_signed_out_callers_get_401(app: TestClient, method: str, path: str) -> None:  # noqa: F811
    response = app.request(method, _url(path))
    assert response.status_code == 401, f"{method} {path} answered {response.status_code} to an anonymous caller"


@pytest.mark.parametrize(
    ("method", "path"),
    [(m, p) for m, p, _ in _operations() if p.startswith("/api/admin/") or (m, p) in ADMIN_ONLY_EXTRA],
)
def test_members_get_403_on_admin_routes(app: TestClient, test_engine: Engine, provider, method: str, path: str) -> None:  # noqa: F811
    member = sign_in(TestClient(app.app), test_engine, make_user(test_engine, "member"))
    response = member.request(method, _url(path), json={} if method != "GET" else None)
    assert response.status_code == 403, f"{method} {path} answered {response.status_code} to a member"
