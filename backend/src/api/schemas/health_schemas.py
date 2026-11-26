"""Pydantic schemas for connectivity checks."""

from __future__ import annotations

from pydantic import BaseModel


class NetworkCheck(BaseModel):
    name: str
    ok: bool
    detail: str


class NetworkHealthResponse(BaseModel):
    provider: str
    host: str | None
    skipped: bool
    checks: list[NetworkCheck]


class VerifyResponse(BaseModel):
    provider: str
    ok: bool
    error: str | None = None
