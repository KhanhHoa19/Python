import { describe, expect, it } from 'vitest';
import { DURATION_OPTIONS, describeFilters, formatDuration, toggleSlug } from './recommend.ts';

describe('recommend helpers', () => {
  it('toggles a category in and out, keeping the order', () => {
    expect(toggleSlug(['a'], 'b')).toEqual(['a', 'b']);
    expect(toggleSlug(['a', 'b'], 'a')).toEqual(['b']);
  });

  it('formats durations for people', () => {
    expect(formatDuration(0)).toBe('~1 phút');
    expect(formatDuration(25)).toBe('~25 phút');
    expect(formatDuration(60)).toBe('~1 giờ');
    expect(formatDuration(125)).toBe('~2 giờ 5 phút');
  });

  it('offers "any length" first and ascending limits after it', () => {
    expect(DURATION_OPTIONS[0].minutes).toBeNull();
    const limits = DURATION_OPTIONS.slice(1).map((o) => o.minutes as number);
    expect([...limits].sort((a, b) => a - b)).toEqual(limits);
  });

  it('describes the active filters, or nothing', () => {
    expect(describeFilters(null, DURATION_OPTIONS[0])).toBe('');
    expect(describeFilters('Hồi hộp', DURATION_OPTIONS[2])).toBe('Đang lọc: tâm trạng hồi hộp, ≤ 30 phút');
  });
});
