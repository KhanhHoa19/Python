"""The chime played when the story moves on to a new chapter (synthesised: no audio file to ship).

Same notes and length as apps/web/src/lib/chime.ts: E5 then A5, about 1.6 seconds, kept quiet."""

from __future__ import annotations

import io
import math
import struct
import wave

SAMPLE_RATE = 22050
CHIME_SECONDS = 1.6
CHIME_NOTES = ((659.25, 0.0), (880.0, 0.28))  # (frequency in Hz, start in seconds)
PEAK = 0.35  # of full scale: soft enough not to startle a drowsy listener
_ATTACK = 0.03


def make_chime_wav() -> bytes:
    """A mono 16-bit WAV of the chime."""
    total = int(SAMPLE_RATE * CHIME_SECONDS)
    samples = [0.0] * total
    for frequency, start in CHIME_NOTES:
        first = int(start * SAMPLE_RATE)
        length = total - first
        for n in range(length):
            t = n / SAMPLE_RATE
            attack = min(t / _ATTACK, 1.0)
            decay = math.exp(-4.0 * t / (CHIME_SECONDS - start))  # dies away to almost nothing at the end
            samples[first + n] += math.sin(2 * math.pi * frequency * t) * attack * decay
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s * PEAK / 1.2)) * 32767)) for s in samples))
    return buffer.getvalue()
