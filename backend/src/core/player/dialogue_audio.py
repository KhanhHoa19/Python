"""Audio of one sentence read by two voices: the narrator's and the characters'.

Each segment (see core/audio/dialogue.py) is synthesized with its own voice through the normal cache, then the
pieces are joined into one file that is cached under its own key. Clients therefore need no change in how they
play a sentence: they only say which voice speaks the dialogue."""

from __future__ import annotations

import io
import wave
from pathlib import Path

from sqlalchemy import Engine

from src.core.audio.dialogue import has_dialogue, quote_states, split_sentence
from src.core.models.book import BookSentence
from src.core.player.audio_service import active_provider, get_or_create_audio
from src.core.player.cache_manager import AudioCacheManager
from src.core.storage.repositories import SqlBookRepository

_STATES: dict[int, tuple[tuple[int, str], dict[int, bool]]] = {}
_MAX_BOOKS = 8


def quote_states_for(engine: Engine, book_id: int, sentences: list[BookSentence] | None = None) -> dict[int, bool]:
    """sentence_index -> a quotation is already open when it starts. Kept in memory per book (it only depends on the text)."""
    book_sentences = sentences or SqlBookRepository(engine).get_book_sentences(book_id)
    ordered = sorted(book_sentences, key=lambda s: s.sentence_index)
    fingerprint = (len(ordered), ordered[-1].content_hash if ordered else "")
    cached = _STATES.get(book_id)
    if cached and cached[0] == fingerprint:
        return cached[1]
    states = dict(zip((s.sentence_index for s in ordered), quote_states([s.text_content for s in ordered]), strict=True))
    if len(_STATES) >= _MAX_BOOKS:
        _STATES.pop(next(iter(_STATES)))
    _STATES[book_id] = (fingerprint, states)
    return states


def _join(paths: list[Path]) -> tuple[bytes, str]:
    ext = paths[0].suffix.lstrip(".").lower()
    if any(p.suffix.lstrip(".").lower() != ext for p in paths):
        raise ValueError("Audio segments have mixed formats; clear the cache and retry.")
    if ext != "wav":
        return b"".join(p.read_bytes() for p in paths), ext  # MP3/OGG frames can be joined end to end
    out = io.BytesIO()
    params = None
    with wave.open(out, "wb") as target:
        for path in paths:
            with wave.open(str(path), "rb") as src:
                if params is None:
                    params = src.getparams()
                    target.setparams(params)
                elif src.getparams()[:3] != params[:3]:
                    raise ValueError("Audio segments have different WAV formats.")
                target.writeframes(src.readframes(src.getnframes()))
    return out.getvalue(), ext


def get_or_create_dialogue_audio(
    engine: Engine, book_id: int, text: str, in_quote: bool, narrator: str, character: str, speed: float,
) -> Path:
    """Audio of `text` with its dialogue read by `character` and the rest by `narrator`.
    A sentence without dialogue is exactly the ordinary narrator audio (same cache entry as before)."""
    segments, _ = split_sentence(text, in_quote)
    if not has_dialogue(segments) or character == narrator:
        return get_or_create_audio(engine, book_id, text, narrator, speed)[0]

    cache = AudioCacheManager()
    namespace = active_provider(narrator).cache_namespace
    key = AudioCacheManager.compute_key(text, f"{narrator}\x1f{character}\x1fdialogue1", speed, namespace)
    hit = cache.get_cached_audio(book_id, key)
    if hit:
        return hit
    paths = [
        get_or_create_audio(engine, book_id, segment.text, character if segment.dialogue else narrator, speed)[0]
        for segment in segments
    ]
    data, ext = _join(paths)
    return cache.save_audio(book_id, key, data, ext)
