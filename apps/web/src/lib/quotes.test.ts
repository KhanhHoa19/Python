import { describe, expect, it } from 'vitest';
import { EMOTIONS, emotionLabel, matchesQuote, playlistProgress, stepIndex } from './quotes.ts';
import { Note } from '../types/note.ts';

const note = (excerpt: string, note_text = '', book_title = 'Sách'): Note => ({
  id: 1, book_id: 1, book_title, sentence_index: 0, start_offset: 0, end_offset: excerpt.length, excerpt, note_text,
  created_at: '2026-11-26T10:00:00', emotion_tag: null, context_before: '', context_after: '', has_audio: true, voice: null,
});

describe('quotes', () => {
  it('has the four feelings with Vietnamese labels', () => {
    expect(EMOTIONS.map((e) => e.value)).toEqual(['inspiring', 'touching', 'wise', 'funny']);
    expect(emotionLabel('wise')).toBe('Triết lý hay');
    expect(emotionLabel(null)).toBe('');
  });
  it('searches excerpt, note and book title without accents', () => {
    const q = note('Hãy sống thật tử tế', 'điều tôi nhớ', 'Đắc Nhân Tâm');
    expect(matchesQuote(q, 'tu te')).toBe(true);
    expect(matchesQuote(q, 'NHO')).toBe(true);
    expect(matchesQuote(q, 'dac nhan')).toBe(true);
    expect(matchesQuote(q, 'khong co')).toBe(false);
    expect(matchesQuote(q, '  ')).toBe(true);
  });
  it('steps through a playlist and stops at the ends', () => {
    expect(stepIndex(0, 1, 3)).toBe(1);
    expect(stepIndex(2, 1, 3)).toBeNull();
    expect(stepIndex(0, -1, 3)).toBeNull();
    expect(stepIndex(1, -1, 3)).toBe(0);
  });
  it('shows playlist progress', () => {
    expect(playlistProgress(1, 7)).toBe('2 / 7');
    expect(playlistProgress(null, 7)).toBe('');
  });
});
