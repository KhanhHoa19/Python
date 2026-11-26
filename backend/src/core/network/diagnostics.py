"""Socket-based connectivity diagnostics for the active TTS provider (DNS, TCP 443, latency)."""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass

# Fixed allowlist: callers choose a provider name, never an arbitrary host (prevents SSRF).
PROVIDER_HOSTS: dict[str, str] = {
    "edge-tts": "speech.platform.bing.com",
    "openai": "api.openai.com",
}


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def host_for_provider(provider_name: str) -> str | None:
    """Return the network host for a provider, or None for offline providers (e.g. mock)."""
    return PROVIDER_HOSTS.get(provider_name.lower())


def run_network_checks(host: str, port: int = 443, timeout: float = 3.0) -> list[CheckResult]:
    """Run DNS -> TCP port -> latency checks sequentially; later checks are skipped if DNS fails."""
    results: list[CheckResult] = []
    try:
        ip = str(socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)[0][4][0])
        results.append(CheckResult("dns", True, f"{host} -> {ip}"))
    except OSError as exc:
        results.append(CheckResult("dns", False, f"DNS lookup failed: {exc}"))
        return results

    latencies: list[float] = []
    port_error: str | None = None
    for _ in range(3):
        start = time.perf_counter()
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                latencies.append((time.perf_counter() - start) * 1000.0)
        except OSError as exc:
            port_error = str(exc)
            break

    if port_error is not None and not latencies:
        results.append(CheckResult("port", False, f"Port {port} unreachable: {port_error}"))
        return results
    results.append(CheckResult("port", True, f"Port {port} open"))
    results.append(CheckResult("latency", True, f"{sum(latencies) / len(latencies):.0f} ms"))
    return results
