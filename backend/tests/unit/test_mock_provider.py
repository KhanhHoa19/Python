"""MockProvider: simulated latency and failure rate (used to measure the player offline)."""

from __future__ import annotations

import pytest

from src.core.config import get_settings
from src.core.tts.base import TTSProviderError
from src.core.tts.factory import TTSFactory
from src.core.tts.mock_adapter import MockProvider


def failures(provider: MockProvider, calls: int) -> list[bool]:
    outcome: list[bool] = []
    for i in range(calls):
        try:
            provider.synthesize(f"câu số {i}")
            outcome.append(False)
        except TTSProviderError:
            outcome.append(True)
    return outcome


def test_default_mock_never_fails_and_does_not_sleep() -> None:
    slept: list[float] = []
    provider = MockProvider(sleep=slept.append)
    assert not any(failures(provider, 50)) and slept == []


def test_latency_is_applied_to_every_call() -> None:
    slept: list[float] = []
    provider = MockProvider(latency_seconds=1.5, sleep=slept.append)
    provider.synthesize("một câu")
    provider.synthesize("hai câu")
    assert slept == [1.5, 1.5]


def test_jitter_varies_the_latency_within_bounds_and_is_reproducible() -> None:
    def waits(seed: int) -> list[float]:
        slept: list[float] = []
        provider = MockProvider(latency_seconds=2.5, jitter_seconds=1.5, seed=seed, sleep=slept.append)
        for i in range(200):
            provider.synthesize(f"câu {i}")
        return slept

    first = waits(1)
    assert all(1.0 <= w <= 4.0 for w in first)
    assert max(first) - min(first) > 2.0 and 2.3 < sum(first) / len(first) < 2.7  # spread out, centred on 2.5
    assert first == waits(1) and first != waits(2)


def test_jitter_never_makes_a_negative_wait() -> None:
    slept: list[float] = []
    provider = MockProvider(latency_seconds=0.1, jitter_seconds=5.0, seed=3, sleep=slept.append)
    for i in range(100):
        provider.synthesize(f"câu {i}")
    assert min(slept) >= 0.0


def test_error_rate_one_always_fails_and_zero_never_fails() -> None:
    assert all(failures(MockProvider(error_rate=1.0), 20))
    assert not any(failures(MockProvider(error_rate=0.0), 20))


def test_failures_take_the_latency_first_like_a_real_service() -> None:
    slept: list[float] = []
    provider = MockProvider(latency_seconds=2.0, error_rate=1.0, sleep=slept.append)
    with pytest.raises(TTSProviderError, match="Simulated"):
        provider.synthesize("x")
    assert slept == [2.0]


def test_seeded_failures_are_reproducible_and_close_to_the_rate() -> None:
    first = failures(MockProvider(error_rate=0.3, seed=42), 400)
    second = failures(MockProvider(error_rate=0.3, seed=42), 400)
    other = failures(MockProvider(error_rate=0.3, seed=43), 400)
    assert first == second and first != other
    assert 90 <= sum(first) <= 150  # about 30% of 400 (a loose bound; the seed makes it exact)


@pytest.mark.parametrize(("kwargs", "message"), [({"error_rate": 1.5}, "error_rate"), ({"error_rate": -0.1}, "error_rate"),
                                                ({"latency_seconds": -1}, "latency"),
                                                 ({"jitter_seconds": -1}, "jitter")])
def test_invalid_settings_are_rejected(kwargs: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        MockProvider(**kwargs)


def test_empty_text_still_fails_before_any_simulation() -> None:
    slept: list[float] = []
    with pytest.raises(TTSProviderError, match="empty"):
        MockProvider(latency_seconds=1, sleep=slept.append).synthesize("  ")
    assert slept == []


def test_factory_reads_the_mock_knobs_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("TTS_PROVIDER", "mock")
    monkeypatch.setenv("MOCK_TTS_LATENCY_SECONDS", "0.25")
    monkeypatch.setenv("MOCK_TTS_JITTER_SECONDS", "0.5")
    monkeypatch.setenv("MOCK_TTS_ERROR_RATE", "0.1")
    monkeypatch.setenv("MOCK_TTS_SEED", "7")
    get_settings.cache_clear()
    try:
        provider, again = TTSFactory.create_provider(), TTSFactory.create_provider()
        assert isinstance(provider, MockProvider)
        assert (provider._latency, provider._jitter, provider._error_rate) == (0.25, 0.5, 0.1)
        provider._sleep = again._sleep = lambda seconds: None  # do not really wait 0.25 s per call
        assert failures(provider, 300) == failures(again, 300)  # same seed, same failure pattern
    finally:
        get_settings.cache_clear()
