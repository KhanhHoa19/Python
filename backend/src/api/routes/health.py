"""Health API router: provider connectivity diagnostics and credential verification."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.schemas.health_schemas import NetworkCheck, NetworkHealthResponse, VerifyResponse
from src.core.network.diagnostics import host_for_provider, run_network_checks
from src.core.tts.base import TTSProviderError
from src.core.tts.factory import TTSFactory

router = APIRouter(tags=["health"])


@router.get("/health/network", response_model=NetworkHealthResponse)
def network_health() -> NetworkHealthResponse:
    """DNS, TCP 443 and latency checks against the active provider's host."""
    provider = TTSFactory.create_provider()
    host = host_for_provider(provider.provider_name)
    if host is None:
        return NetworkHealthResponse(provider=provider.provider_name, host=None, skipped=True, checks=[])
    checks = [NetworkCheck(name=c.name, ok=c.ok, detail=c.detail) for c in run_network_checks(host)]
    return NetworkHealthResponse(provider=provider.provider_name, host=host, skipped=False, checks=checks)


@router.post("/tts/verify", response_model=VerifyResponse)
def verify_tts() -> VerifyResponse:
    """Synthesize one short sentence to confirm the provider key and connectivity work."""
    provider = TTSFactory.create_provider()
    try:
        provider.verify()
    except TTSProviderError as exc:
        return VerifyResponse(provider=provider.provider_name, ok=False, error=str(exc))
    return VerifyResponse(provider=provider.provider_name, ok=True)
