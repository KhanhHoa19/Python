import { describe, expect, it } from 'vitest';
import { pickInitialTab, playLabel } from './shelf.ts';

describe('shelf tabs', () => {
  it('opens the first tab that has books, in the order of the tabs', () => {
    expect(pickInitialTab({ reading: 2, unread: 5, completed: 1, favorite: 3 })).toBe('reading');
    expect(pickInitialTab({ reading: 0, unread: 5, completed: 1, favorite: 3 })).toBe('unread');
    expect(pickInitialTab({ reading: 0, unread: 0, completed: 0, favorite: 4 })).toBe('favorite');
  });
  it('falls back to "reading" for an empty shelf', () => {
    expect(pickInitialTab({ reading: 0, unread: 0, completed: 0, favorite: 0 })).toBe('reading');
  });
  it('labels the primary button by status', () => {
    expect(playLabel('reading')).toBe('Nghe tiếp');
    expect(playLabel('completed')).toBe('Nghe lại');
    expect(playLabel('unread')).toBe('Bắt đầu nghe');
    expect(playLabel(undefined)).toBe('Bắt đầu nghe');
  });
});
