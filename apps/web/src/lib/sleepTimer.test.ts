import { describe, expect, it } from 'vitest';
import { fadeVolume, formatRemaining, isLastOfChapter, parseCustomMinutes, sleepLabel } from './sleepTimer.ts';

describe('sleep timer rules', () => {
  it('stays at full volume until the last 10 seconds, then fades linearly to 0', () => {
    expect(fadeVolume(600)).toBe(1);
    expect(fadeVolume(10)).toBe(1);
    expect(fadeVolume(5)).toBeCloseTo(0.5);
    expect(fadeVolume(1)).toBeCloseTo(0.1);
    expect(fadeVolume(0)).toBe(0);
    expect(fadeVolume(-3)).toBe(0);
  });
  it('fades over a shorter window when the last sentence is short', () => {
    expect(fadeVolume(2, 4)).toBeCloseTo(0.5);
    expect(fadeVolume(4, 4)).toBe(1);
    expect(fadeVolume(1, 0)).toBe(0);
  });
  it('formats the remaining time, rounding up', () => {
    expect(formatRemaining(750)).toBe('12:30');
    expect(formatRemaining(0.2)).toBe('00:01');
    expect(formatRemaining(0)).toBe('00:00');
    expect(formatRemaining(-5)).toBe('00:00');
    expect(formatRemaining(3600)).toBe('60:00');
  });
  it('finds chapter ends', () => {
    const s = [1, 1, 2, 2, 2, 3].map((chapter_index) => ({ chapter_index }));
    expect([0, 1, 2, 3, 4, 5].map((i) => isLastOfChapter(s, i))).toEqual([false, true, false, false, true, true]);
  });
  it('accepts only whole minutes from 1 to 600', () => {
    expect(parseCustomMinutes('25')).toBe(25);
    expect(parseCustomMinutes(' 600 ')).toBe(600);
    for (const bad of ['', '0', '601', '-5', '1.5', 'abc', '12 phút']) expect(parseCustomMinutes(bad)).toBeNull();
  });
  it('labels the button', () => {
    expect(sleepLabel(null, null)).toBe('Hẹn giờ');
    expect(sleepLabel({ kind: 'chapter' }, null)).toBe('Hết chương');
    expect(sleepLabel({ kind: 'minutes', minutes: 30 }, 1500)).toBe('25:00');
    expect(sleepLabel({ kind: 'minutes', minutes: 30 }, null)).toBe('30:00');
  });
});
