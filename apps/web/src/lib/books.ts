import { BookWithProgress } from '../types/book.ts';
import { normalizeText, parseIso } from './format.ts';

export const SORT_OPTIONS = ['Đọc gần đây', 'Tên A→Z', 'Ngày thêm', 'Tiến độ'] as const;
export type SortOption = (typeof SORT_OPTIONS)[number];

export function progressFraction(book: BookWithProgress): number {
  const pct = book.bookmark?.completion_percentage ?? 0;
  return Math.min(Math.max(pct / 100, 0), 1);
}

function time(value: string | null | undefined): number {
  return parseIso(value)?.getTime() ?? 0;
}

export function filterAndSortBooks(books: BookWithProgress[], query: string, sort: SortOption): BookWithProgress[] {
  const needle = normalizeText(query.trim());
  const items = books.filter((b) => normalizeText(`${b.title} ${b.author}`).includes(needle));
  switch (sort) {
    case 'Tên A→Z':
      return items.sort((a, b) => normalizeText(a.title).localeCompare(normalizeText(b.title)));
    case 'Ngày thêm':
      return items.sort((a, b) => time(b.created_at) - time(a.created_at));
    case 'Tiến độ':
      return items.sort((a, b) => progressFraction(b) - progressFraction(a));
    default:
      return items.sort((a, b) => time(b.bookmark?.last_read_at) - time(a.bookmark?.last_read_at));
  }
}

/** The book to resume on startup: read before (0 < progress < 100%), latest read first. */
export function mostRecentUnfinished(books: BookWithProgress[]): BookWithProgress | null {
  const candidates = books.filter((b) => {
    const p = progressFraction(b);
    return p > 0 && p < 1 && !!b.bookmark?.last_read_at;
  });
  if (!candidates.length) return null;
  return candidates.reduce((best, b) => (time(b.bookmark?.last_read_at) > time(best.bookmark?.last_read_at) ? b : best));
}
