"""ALL-CAPS words must not reach the voice as capitals."""

from __future__ import annotations

import pytest

from src.core.tts.speech_text import prepare_speech_text


@pytest.mark.parametrize(("raw", "spoken"), [
    ("THUNG LŨNG KHỦNG KHIẾP", "Thung lũng khủng khiếp"),
    ("TIN BÁO", "Tin báo"),
    ("“ĐỪNG ĐI!”", "“Đừng đi!”"),
    ("Anh ta hét lên: ĐỨNG LẠI NGAY!", "Anh ta hét lên: đứng lại ngay!"),
    ("Tôi làm việc ở NASA và sống ở VN.", "Tôi làm việc ở NASA và sống ở VN."),  # real acronyms stay
    ("Cuộc chiến năm XVIII rất dài.", "Cuộc chiến năm XVIII rất dài."),  # Roman numerals stay
    ("Chương 1: Mở đầu", "Chương 1: Mở đầu"),
    ("Holmes nói: Xin chào.", "Holmes nói: Xin chào."),
    ("VN", "VN"),
    ("123", "123"),
    ("", ""),
])
def test_prepare_speech_text(raw: str, spoken: str) -> None:
    assert prepare_speech_text(raw) == spoken


def test_audio_cache_is_keyed_by_what_is_spoken(test_engine, tmp_path, monkeypatch) -> None:
    """The same title in capitals and in normal case share one synthesis (and one charge)."""
    from unittest.mock import MagicMock

    from src.core.tts.base import AudioSynthesisResult

    monkeypatch.setenv("AUDIO_CACHE_DIR", str(tmp_path))
    from src.core.config import get_settings

    get_settings.cache_clear()
    from src.core.player.audio_service import get_or_create_audio

    provider = MagicMock()
    provider.provider_name, provider.cache_namespace = "mock", "mock"
    provider.synthesize.return_value = AudioSynthesisResult(audio_bytes=b"RIFFxxxx", audio_format="wav", duration_seconds=1.0, response_time_seconds=0.1)
    engine = test_engine
    get_or_create_audio(engine, 1, "TIN BÁO", "v", 1.0, provider)
    assert provider.synthesize.call_args.kwargs["text"] == "Tin báo"
    get_or_create_audio(engine, 1, "Tin báo", "v", 1.0, provider)
    assert provider.synthesize.call_count == 1  # second call came from the cache
    get_settings.cache_clear()
