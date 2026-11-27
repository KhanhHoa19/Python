import { describe, expect, it } from 'vitest';
import { checkBookTitle, mostRecentUnfinished, progressFraction } from './books.ts';
import { formatMinutes, formatNumber, normalizeText, parseIso, usageRatio } from './format.ts';
import { describeVoice } from './voices.ts';
import { BookWithProgress } from '../types/book.ts';

function book(title: string, pct?: number, last?: string, created = '2026-01-01T00:00:00', author = ''): BookWithProgress {
  return {
    id: 1, title, author, total_chapters: 1, total_sentences: 10, total_words: 100, created_at: created,
    progress: pct === undefined ? null : { status: pct >= 100 ? 'completed' : 'reading', is_favorite: false, current_chapter: 1, current_sentence_index: 0, completion_percentage: pct, last_read_at: last ?? null, voice: null },
  };
}

describe('format', () => {
  it('normalizes Vietnamese text', () => expect(normalizeText('Đại Học Bách Khoa')).toBe('dai hoc bach khoa'));
  it('formats minutes', () => {
    expect(formatMinutes(760)).toBe('12 giờ 40');
    expect(formatMinutes(35)).toBe('35 phút');
    expect(formatMinutes(0.2)).toBe('12 giây');
    expect(formatMinutes(0)).toBe('0 phút');
  });
  it('formats numbers with dots', () => {
    expect(formatNumber(96200)).toBe('96.200');
    expect(formatNumber(999)).toBe('999');
    expect(formatNumber(1234567)).toBe('1.234.567');
  });
  it('treats naive timestamps as UTC (what the backend writes)', () => {
    expect(parseIso('2026-11-26T04:37:53')?.toISOString()).toBe('2026-11-26T04:37:53.000Z');
    expect(parseIso('2026-11-26T04:37:53+07:00')?.toISOString()).toBe('2026-11-25T21:37:53.000Z');
    expect(parseIso('garbage')).toBeNull();
  });
  it('computes usage ratio', () => {
    expect(usageRatio(25, 100)).toBe(0.25);
    expect(usageRatio(500, 100)).toBe(1);
    expect(usageRatio(10, 0)).toBe(0);
  });
});

describe('books', () => {
  it('turns progress into a fraction between 0 and 1', () => {
    expect(progressFraction(book('a'))).toBe(0);
    expect(progressFraction(book('a', 42.5))).toBeCloseTo(0.425);
    expect(progressFraction(book('a', 180))).toBe(1);
  });
  it('resumes the most recent unfinished book', () => {
    const books = [book('new'), book('done', 100, '2026-05-01T00:00:00'), book('a', 20, '2026-02-01T00:00:00'), book('b', 50, '2026-04-01T00:00:00')];
    expect(mostRecentUnfinished(books)?.title).toBe('b');
    expect(mostRecentUnfinished([book('new'), book('done', 100, '2026-05-01T00:00:00')])).toBeNull();
  });
});

describe('voices', () => {
  it('describes a voice', () => {
    const v = { voice_id: 'x', display_name: 'Hoài My', provider: 'p', language: 'vi', gender: 'female', style: 'kể chuyện', is_custom: false, consent_at: null };
    expect(describeVoice(v)).toBe('Hoài My · Nữ · kể chuyện');
    expect(describeVoice({ ...v, is_custom: true, style: null, gender: null })).toBe('Hoài My · Giọng của tôi');
  });
});

describe('checkBookTitle', () => {
  it('trims and collapses whitespace', () => {
    expect(checkBookTitle('  Sherlock   Holmes \n tập một ')).toEqual({ ok: true, title: 'Sherlock Holmes tập một' });
  });
  it('rejects empty and whitespace-only titles', () => {
    for (const raw of ['', '   ', '\n\t']) expect(checkBookTitle(raw)).toMatchObject({ ok: false });
  });
  it('allows exactly 255 characters and rejects 256', () => {
    expect(checkBookTitle('ế'.repeat(255))).toMatchObject({ ok: true });
    expect(checkBookTitle('ế'.repeat(256))).toMatchObject({ ok: false });
  });
});
