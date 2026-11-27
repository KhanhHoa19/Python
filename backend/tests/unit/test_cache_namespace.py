"""Audio cache keys carry the provider (and model); old cache entries are adopted, not lost."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from sqlalchemy import Engine

from src.core.config import get_settings
from src.core.player.audio_service import get_or_create_audio, is_cached
from src.core.player.cache_manager import AudioCacheManager, voice_provider_hint
from src.core.storage.repositories import SqlSettingsRepository
from src.core.tts.mock_adapter import MockProvider

HEYGEN_VOICE = "a" * 32
TEXT = "Xin chào các bạn."


class NamedProvider(MockProvider):
    """A mock that pretends to be another provider/model and counts its synthesis calls."""

    def __init__(self, name: str, namespace: str | None = None):
        super().__init__()
        self._name, self._namespace, self.calls = name, namespace or name, 0

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def cache_namespace(self) -> str:
        return self._namespace

    def synthesize(self, text, voice=None, speed=1.0):  # type: ignore[no-untyped-def]
        self.calls += 1
        return super().synthesize(text, voice, speed)


@pytest.fixture
def cache_dir(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("AUDIO_CACHE_DIR", str(tmp_path / "cache"))
    get_settings.cache_clear()
    yield tmp_path / "cache"
    get_settings.cache_clear()


# ---------------------------------------------------------------- keys


def test_namespace_changes_the_key_and_empty_namespace_keeps_the_original_key() -> None:
    original = hashlib.sha256(f"{TEXT}:v1:1.00".encode()).hexdigest()
    assert AudioCacheManager.compute_key(TEXT, "v1", 1.0) == original
    assert AudioCacheManager.compute_key(TEXT, "v1", 1.0, "") == original
    a = AudioCacheManager.compute_key(TEXT, "v1", 1.0, "heygen:turbo")
    b = AudioCacheManager.compute_key(TEXT, "v1", 1.0, "heygen:v1")
    c = AudioCacheManager.compute_key(TEXT, "v1", 1.0, "edge-tts")
    assert len({original, a, b, c}) == 4


@pytest.mark.parametrize(
    ("voice", "expected"),
    [("0263e745d31e4844ab25c21496480775", "heygen"), ("vi-VN-HoaiMyNeural", "edge-tts"),
     ("en-US-ChristopherNeural", "edge-tts"), ("zh-CN-XiaoxiaoNeural", "edge-tts"), ("alloy", "openai"),
     ("mock-vi-female", "mock"), ("my-own-voice", None), ("", None), ("ABCDEF" * 6, None)],
)
def test_voice_provider_hint(voice: str, expected: str | None) -> None:
    assert voice_provider_hint(voice) == expected


# ---------------------------------------------------------------- separation


def test_audio_is_cached_per_provider_and_per_model(test_engine: Engine, cache_dir: Path) -> None:
    turbo = NamedProvider("heygen", "heygen:turbo")
    full = NamedProvider("heygen", "heygen:full")
    other = NamedProvider("edge-tts")

    assert get_or_create_audio(test_engine, 1, TEXT, HEYGEN_VOICE, provider=turbo)[1] is False
    assert get_or_create_audio(test_engine, 1, TEXT, HEYGEN_VOICE, provider=turbo)[1] is True   # same model: hit
    assert get_or_create_audio(test_engine, 1, TEXT, HEYGEN_VOICE, provider=full)[1] is False   # other model: miss
    assert get_or_create_audio(test_engine, 1, TEXT, HEYGEN_VOICE, provider=other)[1] is False  # other provider
    assert (turbo.calls, full.calls, other.calls) == (1, 1, 1)
    assert len(list((cache_dir / "1").iterdir())) == 3


def test_is_cached_follows_the_provider(test_engine: Engine, cache_dir: Path) -> None:
    provider = NamedProvider("mock")
    assert not is_cached(1, TEXT, "mock-vi-female", 1.0, provider)
    get_or_create_audio(test_engine, 1, TEXT, "mock-vi-female", provider=provider)
    assert is_cached(1, TEXT, "mock-vi-female", 1.0, provider)
    assert not is_cached(1, TEXT, "mock-vi-female", 1.0, NamedProvider("mock", "mock:other"))


# ---------------------------------------------------------------- adopting old entries


def legacy_entry(cache_dir: Path, scope: int, text: str, voice: str, speed: float, data: bytes, ext: str) -> Path:
    folder = cache_dir / str(scope)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{AudioCacheManager.compute_key(text, voice, speed)}.{ext}"
    path.write_bytes(data)
    return path


def test_legacy_entry_of_the_active_provider_is_adopted_not_regenerated(test_engine: Engine, cache_dir: Path) -> None:
    old = legacy_entry(cache_dir, 5, TEXT, HEYGEN_VOICE, 1.0, b"ID3-old-heygen-audio", "mp3")
    provider = NamedProvider("heygen", "heygen:turbo")

    path, from_cache = get_or_create_audio(test_engine, 5, TEXT, HEYGEN_VOICE, provider=provider)

    assert from_cache is True and provider.calls == 0  # nothing was synthesized (and nothing paid for)
    assert path.read_bytes() == b"ID3-old-heygen-audio" and path.suffix == ".mp3"
    assert not old.exists()  # renamed, not copied
    assert path.stem == AudioCacheManager.compute_key(TEXT, HEYGEN_VOICE, 1.0, "heygen:turbo")
    assert SqlSettingsRepository(test_engine).chars_used_today() == 0  # no quota used for a cache hit
    assert get_or_create_audio(test_engine, 5, TEXT, HEYGEN_VOICE, provider=provider)[0] == path  # now a normal hit


def test_legacy_entry_of_another_provider_is_left_alone(test_engine: Engine, cache_dir: Path) -> None:
    edge_entry = legacy_entry(cache_dir, 5, TEXT, "vi-VN-HoaiMyNeural", 1.0, b"edge-audio", "mp3")
    provider = NamedProvider("heygen", "heygen:turbo")

    path, from_cache = get_or_create_audio(test_engine, 5, TEXT, "vi-VN-HoaiMyNeural", provider=provider)

    assert from_cache is False and provider.calls == 1  # an Edge voice is not a HeyGen voice: synthesize anew
    assert edge_entry.exists() and edge_entry.read_bytes() == b"edge-audio" and path != edge_entry


def test_legacy_entry_for_an_unrecognised_voice_is_not_adopted(test_engine: Engine, cache_dir: Path) -> None:
    entry = legacy_entry(cache_dir, 5, TEXT, "my-own-voice", 1.0, b"???", "mp3")
    provider = NamedProvider("heygen")
    assert get_or_create_audio(test_engine, 5, TEXT, "my-own-voice", provider=provider)[1] is False
    assert entry.exists()


def test_adoption_respects_speed_and_scope(test_engine: Engine, cache_dir: Path) -> None:
    legacy_entry(cache_dir, 5, TEXT, HEYGEN_VOICE, 1.25, b"fast", "mp3")
    provider = NamedProvider("heygen")
    assert get_or_create_audio(test_engine, 5, TEXT, HEYGEN_VOICE, 1.0, provider=provider)[1] is False  # other speed
    assert get_or_create_audio(test_engine, 6, TEXT, HEYGEN_VOICE, 1.25, provider=provider)[1] is False  # other book
    assert get_or_create_audio(test_engine, 5, TEXT, HEYGEN_VOICE, 1.25, provider=provider)[1] is True


def test_is_cached_sees_adoptable_legacy_audio(test_engine: Engine, cache_dir: Path) -> None:
    legacy_entry(cache_dir, 5, TEXT, HEYGEN_VOICE, 1.0, b"old", "mp3")
    assert is_cached(5, TEXT, HEYGEN_VOICE, 1.0, NamedProvider("heygen"))
    assert not is_cached(5, TEXT, HEYGEN_VOICE, 1.0, NamedProvider("edge-tts"))
