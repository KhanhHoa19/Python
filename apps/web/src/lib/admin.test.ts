import { describe, expect, it } from 'vitest';
import { categoryProblem, formatBytes, sortSystemBooks } from './admin.ts';
import { cloneQuota, describeVoice, splitVoices, systemDefault } from './voices.ts';
import { AdminBook } from '../types/admin.ts';
import { Voice, VoiceList } from '../types/voice.ts';

const book = (id: number, title: string, is_public: boolean): AdminBook => ({ id, title, author: '', total_chapters: 1, is_public, is_mine: true, category: null, cover_url: null, shelf_count: 0 });
const voice = (id: string, extra: Partial<Voice> = {}): Voice => ({ voice_id: id, display_name: id, provider: 'x', language: 'vi', gender: null, style: null, is_custom: false, consent_at: null, ...extra });
const list = (extra: Partial<VoiceList>): VoiceList => ({ provider: 'x', supports_cloning: true, clone_sample_seconds: [5, 15], voices: [], warning: null, ...extra });

describe('admin helpers', () => {
  it('lists public books first, then by title', () => {
    const sorted = sortSystemBooks([book(1, 'Zeta', false), book(2, 'Đông', true), book(3, 'An', true)]);
    expect(sorted.map((b) => b.id)).toEqual([3, 2, 1]);
  });

  it('explains why a category cannot be saved', () => {
    expect(categoryProblem('  ', '#112233')).toMatch(/tên/);
    expect(categoryProblem('Sử', 'red')).toMatch(/Màu/);
    expect(categoryProblem('Sử', '#A1B2c3')).toBeNull();
  });
});

describe('file sizes', () => {
  it('formats sizes for humans', () => {
    expect(formatBytes(1913661)).toBe('1,8 MB');
    expect(formatBytes(300)).toBe('1 KB');
    expect(formatBytes(512 * 1024)).toBe('512 KB');
  });
});

describe('voice studio helpers', () => {
  it('splits system voices from the user own clones', () => {
    const voices = [voice('p'), voice('pub', { is_custom: true, is_public: true, is_mine: false }), voice('mine', { is_custom: true, is_mine: true }), voice('mypub', { is_custom: true, is_public: true, is_mine: true })];
    const { system, mine } = splitVoices(voices);
    expect(system.map((v) => v.voice_id)).toEqual(['p', 'pub']);
    expect(mine.map((v) => v.voice_id)).toEqual(['mine', 'mypub']);
  });

  it('counts the clone allowance', () => {
    expect(cloneQuota(list({ my_voice_count: 2, max_voices: 3 }))).toEqual({ used: 2, max: 3, left: 1, full: false });
    expect(cloneQuota(list({ my_voice_count: 3, max_voices: 3 })).full).toBe(true);
    expect(cloneQuota(list({ my_voice_count: 9, max_voices: null }))).toEqual({ used: 9, max: null, left: null, full: false });
    expect(cloneQuota(null).full).toBe(false);
  });

  it('labels a shared voice differently from an own one', () => {
    expect(describeVoice(voice('a', { is_custom: true, is_mine: false }))).toContain('Giọng chung');
    expect(describeVoice(voice('a', { is_custom: true, is_mine: true }))).toContain('Giọng của tôi');
  });

  it('finds the system default only when it still exists', () => {
    const voices = [voice('a')];
    expect(systemDefault(list({ voices, system_default_voice: 'a' }))?.voice_id).toBe('a');
    expect(systemDefault(list({ voices, system_default_voice: 'gone' }))).toBeNull();
    expect(systemDefault(list({ voices, system_default_voice: '' }))).toBeNull();
  });
});
