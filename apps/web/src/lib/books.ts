import { BookWithProgress } from '../types/book.ts';
import { parseIso } from './format.ts';

export function progressFraction(book: BookWithProgress): number {
  const pct = book.progress?.completion_percentage ?? 0;
  return Math.min(Math.max(pct / 100, 0), 1);
}

function time(value: string | null | undefined): number {
  return parseIso(value)?.getTime() ?? 0;
}

/** The book to resume on startup: being read (0 < progress < 100%), most recently read first. */
export function mostRecentUnfinished(books: BookWithProgress[]): BookWithProgress | null {
  const candidates = books.filter((b) => {
    const p = progressFraction(b);
    return p > 0 && p < 1 && !!b.progress?.last_read_at;
  });
  if (!candidates.length) return null;
  return candidates.reduce((best, b) => (time(b.progress?.last_read_at) > time(best.progress?.last_read_at) ? b : best));
}

export const MAX_TITLE_LENGTH = 255;

export type TitleCheck = { ok: true; title: string } | { ok: false; error: string };

/** Same rules as the backend: trim, collapse inner whitespace, 1-255 characters. */
export function checkBookTitle(raw: string): TitleCheck {
  const title = raw.split(/\s+/).filter(Boolean).join(' ');
  if (!title) return { ok: false, error: 'Tên không được để trống.' };
  if (title.length > MAX_TITLE_LENGTH) return { ok: false, error: `Tên tối đa ${MAX_TITLE_LENGTH} ký tự.` };
  return { ok: true, title };
}
