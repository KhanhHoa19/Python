import { describe, expect, it } from 'vitest';
import { chapterAt, describeChapter } from './chapters.ts';
import { Chapter } from '../types/book.ts';

const chapter = (i: number, start: number, end: number): Chapter => ({
  chapter_index: i, title: `Chương ${i}`, start_sentence_index: start, end_sentence_index: end, sentence_count: end - start + 1, word_count: 10,
});
const chapters = [chapter(1, 0, 4), chapter(2, 5, 9), chapter(3, 10, 10)];

describe('chapters', () => {
  it('finds the chapter containing a sentence, including its first and last sentence', () => {
    expect([0, 4, 5, 9, 10].map((i) => chapterAt(chapters, i)?.chapter_index)).toEqual([1, 1, 2, 2, 3]);
  });
  it('falls back to the nearest chapter outside the range and to null when there are none', () => {
    expect(chapterAt(chapters, -3)?.chapter_index).toBe(1);
    expect(chapterAt(chapters, 99)?.chapter_index).toBe(3);
    expect(chapterAt([], 0)).toBeNull();
  });
  it('describes a chapter', () => {
    expect(describeChapter(chapter(1, 0, 4), (n) => String(n))).toBe('5 câu · 10 từ');
  });
});
