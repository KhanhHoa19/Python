import { describe, expect, it } from 'vitest';
import { coverHue, coverInitials } from './cover.ts';

describe('cover', () => {
  it('gives the same hue to the same title, within 0-359', () => {
    expect(coverHue('Sherlock Holmes')).toBe(coverHue('Sherlock Holmes'));
    for (const title of ['', 'a', 'Đắc Nhân Tâm', 'x'.repeat(500)]) {
      const hue = coverHue(title);
      expect(hue).toBeGreaterThanOrEqual(0);
      expect(hue).toBeLessThan(360);
    }
  });
  it('spreads different titles over different hues', () => {
    const hues = new Set(['Một', 'Hai', 'Ba', 'Bốn', 'Năm', 'Sáu'].map(coverHue));
    expect(hues.size).toBeGreaterThan(3);
  });
  it('takes initials of the first two words, keeping Vietnamese letters', () => {
    expect(coverInitials('Đắc Nhân Tâm')).toBe('ĐN');
    expect(coverInitials('  sherlock   holmes  ')).toBe('SH');
    expect(coverInitials('Python')).toBe('P');
    expect(coverInitials('— ...')).toBe('♪');
  });
});
