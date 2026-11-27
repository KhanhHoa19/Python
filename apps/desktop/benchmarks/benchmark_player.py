"""Measure the silence between sentences of the REAL PlaybackEngine under simulated TTS conditions.

What is simulated: the TTS service (MockProvider: latency, jitter, failure rate, optional
requests-per-minute limit) and the speaker (a sound that "plays" for as long as the sentence would
take to say). What is real: PlaybackEngine, its threads, its bounded queue, its retry/skip logic.

Metrics per run (a run reads N sentences once):
  first audio : seconds from pressing play to the first sound
  gap         : silence between the end of one sentence and the start of the next
  stall       : a gap longer than STALL_SECONDS (an audible break)
  silence     : share of the time after the first sound that nothing was playing

Usage (from apps/desktop):
    python -m benchmarks.benchmark_player --out ../../docs/benchmarks/player_prefetch.md
    python -m benchmarks.benchmark_player --quick          # a few seconds, to check the tool works
"""

from __future__ import annotations

import argparse
import inspect
import json
import random
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from itertools import pairwise
from pathlib import Path

DESKTOP_DIR = Path(__file__).resolve().parents[1]
for extra in (DESKTOP_DIR, DESKTOP_DIR.parents[1] / "backend"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from src.core.tts.base import TTSProviderError
from src.core.tts.mock_adapter import MockProvider

from api_client import ApiError
from player.engine import EngineCallbacks, PlaybackEngine

STALL_SECONDS = 0.3
DEFAULT_SEC_PER_WORD = 0.28  # measured on the cloned voice (hayami: 0.40, so 0.28 is the harder case)
SPEEDS = (0.75, 1.0, 1.5)
PREFETCH = (1, 2, 3, 4, 5)


@dataclass(frozen=True)
class Scenario:
    name: str
    latency: float
    jitter: float = 0.0
    requests_per_minute: int | None = None
    error_rates: tuple[float, ...] = (0.0,)


SCENARIOS = (
    Scenario("0.2 s", 0.2),
    Scenario("1 s", 1.0, error_rates=(0.0, 0.1)),
    Scenario("3 s", 3.0),
    Scenario("HeyGen-like (3 s ±1, 28/min)", 3.0, jitter=1.0, requests_per_minute=28, error_rates=(0.0, 0.1)),
)


@dataclass
class RunResult:
    scenario: str
    error_rate: float
    speed: float
    prefetch: int
    fetch_workers: int
    sentences: int
    played: int
    skipped: int
    first_audio: float
    gaps: list[float]
    audio_seconds: float
    wall_seconds: float

    @property
    def transitions(self) -> int:
        return len(self.gaps)

    @property
    def stalls(self) -> int:
        return sum(1 for gap in self.gaps if gap > STALL_SECONDS)

    @property
    def silence_share(self) -> float:
        silence = sum(self.gaps)
        total = silence + self.audio_seconds
        return silence / total if total else 0.0


class SlidingWindowLimiter:
    """At most `max_calls` per minute, like a provider rate limit."""

    def __init__(self, max_calls: int, period: float = 60.0):
        self.max_calls, self.period = max_calls, period
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def wait(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= self.period:
                    self._calls.popleft()
                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return
                delay = self.period - (now - self._calls[0])
            time.sleep(max(delay, 0.01))


class SimulatedSpeaker:
    """An AudioOutput that 'plays' each sentence for its duration at the chosen speed."""

    def __init__(self, durations: Sequence[float], speed: float):
        self._durations, self._speed = durations, speed
        self._busy_until = 0.0

    def play(self, data: bytes, ext: str) -> float:
        length = self._durations[int(data)] / self._speed
        self._busy_until = time.monotonic() + length
        return length

    def is_busy(self) -> bool:
        return time.monotonic() < self._busy_until

    def pause(self) -> None: ...
    def resume(self) -> None: ...

    def stop(self) -> None:
        self._busy_until = 0.0

    def close(self) -> None: ...


def percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]


def engine_supports_fetch_workers() -> bool:
    return "fetch_workers" in inspect.signature(PlaybackEngine.__init__).parameters


def run_once(
    scenario: Scenario, error_rate: float, speed: float, prefetch: int, fetch_workers: int,
    words: Sequence[int], sec_per_word: float, seed: int,
) -> RunResult:
    durations = [max(0.5, w * sec_per_word) for w in words]  # the minimum mirrors real short utterances
    provider = MockProvider(latency_seconds=scenario.latency, jitter_seconds=scenario.jitter,
                            error_rate=error_rate, seed=seed)
    limiter = SlidingWindowLimiter(scenario.requests_per_minute) if scenario.requests_per_minute else None

    def fetch(index: int) -> tuple[bytes, str]:
        if limiter:
            limiter.wait()
        try:
            provider.synthesize(f"câu số {index}")  # waits (latency) and may fail (error_rate)
        except TTSProviderError as exc:
            raise ApiError(502, str(exc)) from exc
        return str(index).encode(), "wav"

    starts: dict[int, float] = {}
    ends: dict[int, float] = {}
    skipped: list[int] = []
    done = threading.Event()
    callbacks = EngineCallbacks(
        on_start=lambda i: starts.setdefault(i, time.monotonic()),
        on_end=lambda i, seconds: ends.setdefault(i, time.monotonic()),
        on_skip=lambda i, message: skipped.append(i),
        on_finished=done.set,
        on_fatal=lambda message: done.set(),
    )
    kwargs = {"fetch_workers": fetch_workers} if engine_supports_fetch_workers() else {}
    engine = PlaybackEngine(fetch, SimulatedSpeaker(durations, speed), len(words), callbacks, prefetch=prefetch, **kwargs)

    budget = sum(durations) / speed + len(words) * (scenario.latency + scenario.jitter) * 3 + 60
    t0 = time.monotonic()
    engine.start(0)
    finished = done.wait(budget)
    wall = time.monotonic() - t0
    engine.stop()
    if not finished:
        raise RuntimeError(f"run did not finish within {budget:.0f}s: {scenario.name}, speed {speed}, N={prefetch}")

    order = sorted(starts)
    gaps = [max(0.0, starts[b] - ends[a]) for a, b in pairwise(order) if a in ends]
    return RunResult(
        scenario=scenario.name, error_rate=error_rate, speed=speed, prefetch=prefetch, fetch_workers=fetch_workers,
        sentences=len(words), played=len(order), skipped=len(skipped),
        first_audio=(starts[order[0]] - t0) if order else wall, gaps=gaps,
        audio_seconds=sum(durations[i] / speed for i in order), wall_seconds=wall,
    )


def load_word_counts(api_url: str, book_id: int | None, count: int, seed: int) -> tuple[list[int], str]:
    """Word counts of real sentences (so durations follow the real distribution); synthetic if offline."""
    try:
        books = json.load(urllib.request.urlopen(f"{api_url}/api/books", timeout=5))
        books = [b for b in books if book_id in (None, b["id"]) and b["total_sentences"] >= count * 2]
        if not books:
            raise LookupError("no suitable book")
        book = max(books, key=lambda b: b["total_sentences"])
        sentences = json.load(urllib.request.urlopen(f"{api_url}/api/books/{book['id']}/sentences", timeout=20))["sentences"]
        middle = sentences[len(sentences) // 3:]  # skip the table of contents and front matter
        rng = random.Random(seed)
        chosen = rng.sample(middle, count)
        return [max(1, s["word_count"]) for s in chosen], f"book {book['id']} ({book['title']!r}), {count} random sentences"
    except (urllib.error.URLError, LookupError, OSError, KeyError, ValueError):
        rng = random.Random(seed)
        return [max(1, round(rng.lognormvariate(2.1, 0.55))) for _ in range(count)], f"synthetic log-normal sentences (median ~8 words), {count} sentences"


def summarize(results: Sequence[RunResult]) -> dict[str, float]:
    gaps = [g for r in results for g in r.gaps]
    transitions = sum(r.transitions for r in results)
    return {
        "stall_pct": 100.0 * sum(r.stalls for r in results) / transitions if transitions else 0.0,
        "median_gap": statistics.median(gaps) if gaps else 0.0,
        "p95_gap": percentile(gaps, 0.95),
        "silence_pct": 100.0 * statistics.fmean(r.silence_share for r in results) if results else 0.0,
        "first_audio": statistics.fmean(r.first_audio for r in results) if results else 0.0,
        "skipped_pct": 100.0 * sum(r.skipped for r in results) / sum(r.sentences for r in results) if results else 0.0,
    }


def render_markdown(results: Sequence[RunResult], meta: dict[str, object]) -> str:
    keys = sorted({(r.scenario, r.error_rate, r.speed) for r in results},
                  key=lambda k: ([s.name for s in SCENARIOS].index(k[0]), k[1], k[2]))
    prefetches = sorted({r.prefetch for r in results})
    workers = sorted({r.fetch_workers for r in results})

    def table(title: str, metric: str, fmt: Callable[[float], str]) -> list[str]:
        lines = [f"### {title}", ""]
        for w in workers:
            if len(workers) > 1:
                lines += [f"**{w} fetch worker(s)**", ""]
            lines += ["| Độ trễ TTS | Lỗi | Tốc độ | " + " | ".join(f"N={n}" for n in prefetches) + " |",
                      "|---|---|---|" + "---|" * len(prefetches)]
            for scenario, error, speed in keys:
                cells = []
                for n in prefetches:
                    subset = [r for r in results if (r.scenario, r.error_rate, r.speed, r.prefetch, r.fetch_workers) == (scenario, error, speed, n, w)]
                    cells.append(fmt(summarize(subset)[metric]) if subset else "–")
                lines.append(f"| {scenario} | {int(error * 100)}% | {speed}x | " + " | ".join(cells) + " |")
            lines.append("")
        return lines

    out = ["# Đo khoảng lặng giữa các câu (PlaybackEngine thật, TTS mô phỏng)", ""]
    out += [f"- {k}: {v}" for k, v in meta.items()]
    out += ["", f"Ngắt quãng (stall) = khoảng lặng > {STALL_SECONDS} s giữa hai câu. N = số câu tải trước.", ""]
    out += table("Tỷ lệ ngắt quãng (% số lần chuyển câu)", "stall_pct", lambda v: f"{v:.0f}%")
    out += table("Khoảng lặng giữa các câu, phân vị 95 (giây)", "p95_gap", lambda v: f"{v:.2f}")
    out += table("Phần thời gian im lặng (% sau âm thanh đầu tiên)", "silence_pct", lambda v: f"{v:.0f}%")
    out += table("Câu bị bỏ qua do lỗi (% số câu)", "skipped_pct", lambda v: f"{v:.0f}%")
    first = {}
    for r in results:
        first.setdefault(r.scenario, []).append(r.first_audio)
    out += ["### Độ trễ trước âm thanh đầu tiên (giây, trung bình)", "", "| Độ trễ TTS | Giây |", "|---|---|"]
    out += [f"| {name} | {statistics.fmean(values):.1f} |" for name, values in first.items()]
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sentences", type=int, default=12, help="sentences read per run")
    parser.add_argument("--workers", type=int, default=30, help="runs executed at the same time")
    parser.add_argument("--prefetch", type=int, nargs="+", default=list(PREFETCH))
    parser.add_argument("--speeds", type=float, nargs="+", default=list(SPEEDS))
    parser.add_argument("--fetch-workers", type=int, nargs="+", default=[1], help="parallel downloads (needs engine support)")
    parser.add_argument("--sec-per-word", type=float, default=DEFAULT_SEC_PER_WORD)
    parser.add_argument("--api-url", default="http://127.0.0.1:5000")
    parser.add_argument("--book-id", type=int, default=None)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--quick", action="store_true", help="tiny run to check the tool")
    parser.add_argument("--out", type=Path, default=None, help="write the Markdown report here")
    parser.add_argument("--json", type=Path, default=None, help="also write the raw results here")
    args = parser.parse_args()

    scenarios = SCENARIOS[:1] if args.quick else SCENARIOS
    sentences = 4 if args.quick else args.sentences
    prefetches, speeds = (args.prefetch[:2], args.speeds[:1]) if args.quick else (args.prefetch, args.speeds)
    words, source = load_word_counts(args.api_url, args.book_id, sentences, args.seed)
    if any(w > 1 for w in args.fetch_workers) and not engine_supports_fetch_workers():
        print("note: this PlaybackEngine has no fetch_workers option; running with a single downloader", file=sys.stderr)
        args.fetch_workers = [1]

    jobs = [
        (sc, err, speed, n, fw)
        for sc in scenarios for err in sc.error_rates for speed in speeds for n in prefetches for fw in args.fetch_workers
    ]
    print(f"{len(jobs)} runs, {sentences} sentences each, {args.workers} at a time; sentences: {source}", flush=True)
    started = time.monotonic()

    def execute(job: tuple[Scenario, float, float, int, int]) -> RunResult:
        sc, err, speed, n, fw = job
        return run_once(sc, err, speed, n, fw, words, args.sec_per_word, args.seed)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(execute, jobs))
    elapsed = time.monotonic() - started

    meta = {
        "Cách đo": "PlaybackEngine thật; TTS và loa mô phỏng (MockProvider + SimulatedSpeaker)",
        "Câu": source,
        "Tốc độ nói": f"{args.sec_per_word} giây/từ ở 1.0x (giọng clone đo được 0.28; hayami 0.40)",
        "Số lần chạy": f"{len(results)} lần x {sentences} câu, {args.workers} lần chạy song song",
        "Thời gian chạy": f"{elapsed:.0f} giây",
        "Số nguồn tải song song": ", ".join(map(str, args.fetch_workers)),
    }
    report = render_markdown(results, meta)
    print(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"report written to {args.out}")
    if args.json:
        args.json.write_text(json.dumps([asdict(r) for r in results], ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
