import { Chapter } from '../types/book.ts';

/** The chapter that contains sentence `index`, or null if the list is empty. Falls back to the nearest one. */
export function chapterAt(chapters: Chapter[], index: number): Chapter | null {
  if (chapters.length === 0) return null;
  const found = chapters.find((c) => index >= c.start_sentence_index && index <= c.end_sentence_index);
  if (found) return found;
  return index < chapters[0].start_sentence_index ? chapters[0] : chapters[chapters.length - 1];
}

/** "12 câu · 340 từ" under a chapter title. */
export function describeChapter(chapter: Chapter, formatNumber: (n: number) => string): string {
  return `${formatNumber(chapter.sentence_count)} câu · ${formatNumber(chapter.word_count)} từ`;
}
