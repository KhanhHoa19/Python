"""Measure connectivity to candidate TTS providers and optionally synthesize one sentence.

Usage (from backend/):
    python -m scripts.test_connection                 # DNS + TCP 443 + latency for all candidates
    python -m scripts.test_connection --synthesize    # also call the active provider, save output.*

No API key is needed for the network part: it only resolves the host and opens a TCP connection.
"""

from __future__ import annotations

import argparse
import socket
import statistics
import sys
import time
from pathlib import Path

from src.core.network.diagnostics import run_network_checks

# Public API hosts of the providers compared in docs/provider_comparison.md.
CANDIDATE_HOSTS: dict[str, str] = {
    "HeyGen": "api.heygen.com",
    "ElevenLabs": "api.elevenlabs.io",
    "Azure Speech (edge-tts uses the same voices)": "speech.platform.bing.com",
    "Google Cloud TTS": "texttospeech.googleapis.com",
    "OpenAI": "api.openai.com",
    "FPT.AI": "api.fpt.ai",
}
SAMPLE_TEXT = "Xin chào, đây là câu thử giọng đọc tiếng Việt."
SAMPLES = 7


def tcp_latency_ms(host: str, samples: int = SAMPLES) -> list[float]:
    """Time several fresh TCP connects to port 443 (DNS is resolved once, outside the timing)."""
    address = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)[0][4][0]
    timings: list[float] = []
    for _ in range(samples):
        start = time.perf_counter()
        with socket.create_connection((str(address), 443), timeout=5):
            timings.append((time.perf_counter() - start) * 1000.0)
    return timings


def check_hosts() -> int:
    """Print one row per candidate. Returns the number of unreachable hosts."""
    print(f"{'Provider':<46} {'DNS':<4} {'443':<4} {'median ms':>9} {'min':>6} {'max':>6}")
    unreachable = 0
    for name, host in CANDIDATE_HOSTS.items():
        checks = {c.name: c for c in run_network_checks(host)}
        ok = all(checks.get(key) and checks[key].ok for key in ("dns", "port"))
        if not ok:
            unreachable += 1
            reason = next((c.detail for c in checks.values() if not c.ok), "unreachable")
            print(f"{name:<46} {'ok' if checks.get('dns') and checks['dns'].ok else 'FAIL':<4} FAIL  {reason}")
            continue
        try:
            timings = tcp_latency_ms(host)
        except OSError as exc:
            unreachable += 1
            print(f"{name:<46} ok   FAIL  {exc}")
            continue
        print(f"{name:<46} ok   ok   {statistics.median(timings):>9.0f} {min(timings):>6.0f} {max(timings):>6.0f}")
    return unreachable


def synthesize(output_dir: Path) -> int:
    """Call the provider selected by TTS_PROVIDER and save the audio. Needs that provider's key."""
    from src.core.tts.base import TTSProviderError
    from src.core.tts.factory import TTSFactory

    provider = TTSFactory.create_provider()
    print(f"\nSynthesizing with provider '{provider.provider_name}' (voice {provider.default_voice}) ...")
    start = time.perf_counter()
    try:
        result = provider.synthesize(SAMPLE_TEXT)
    except TTSProviderError as exc:
        print(f"FAILED: {exc}")
        return 1
    elapsed = time.perf_counter() - start
    target = output_dir / f"output.{result.audio_format}"
    target.write_bytes(result.audio_bytes)
    print(f"OK: {len(result.audio_bytes)} bytes, {result.audio_format}, {elapsed * 1000:.0f} ms -> {target}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--synthesize", action="store_true", help="also synthesize one sentence with TTS_PROVIDER")
    parser.add_argument("--output-dir", type=Path, default=Path("."), help="where to save output.<ext>")
    args = parser.parse_args()

    status = 1 if check_hosts() else 0
    if args.synthesize:
        status = max(status, synthesize(args.output_dir))
    return status


if __name__ == "__main__":
    sys.exit(main())
