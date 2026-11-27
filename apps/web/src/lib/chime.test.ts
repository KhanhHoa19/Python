import { describe, expect, it } from 'vitest';
import { CHIME_NOTES, CHIME_SECONDS, chimeGain, startsNewChapter } from './chime.ts';

describe('chapter chime', () => {
  it('detects the first sentence of a new chapter', () => {
    const sentences = [1, 1, 2, 2].map((chapter_index) => ({ chapter_index }));
    expect([0, 1, 2, 3].map((i) => startsNewChapter(sentences, i))).toEqual([false, false, true, false]);
    expect(startsNewChapter(sentences, 9)).toBe(false);
  });

  it('keeps the chime quiet and within range', () => {
    expect(chimeGain(1)).toBeLessThan(0.5);
    expect(chimeGain(2)).toBe(chimeGain(1));
    expect(chimeGain(-1)).toBe(0);
  });

  it('fits its notes inside its length', () => {
    expect(CHIME_SECONDS).toBeLessThanOrEqual(2);
    expect(CHIME_NOTES.every((n) => n.start < CHIME_SECONDS)).toBe(true);
  });
});
