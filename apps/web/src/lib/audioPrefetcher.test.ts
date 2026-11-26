import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client.ts';
import { AudioPrefetcher } from './audioPrefetcher.ts';

const blob = (text: string) => new Blob([text]);

describe('AudioPrefetcher', () => {
  let created: string[];
  let revoked: string[];

  beforeEach(() => {
    created = [];
    revoked = [];
    let counter = 0;
    vi.spyOn(URL, 'createObjectURL').mockImplementation(() => {
      const url = `blob:test/${counter++}`;
      created.push(url);
      return url;
    });
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation((url) => {
      revoked.push(url);
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it('fetches the requested sentence and only `ahead` sentences after it', async () => {
    const fetched: number[] = [];
    const prefetcher = new AudioPrefetcher(async (i) => (fetched.push(i), blob(String(i))), 10, 2);
    await prefetcher.get(3);
    await new Promise((r) => setTimeout(r, 0));
    expect(fetched.sort()).toEqual([3, 4, 5]);
  });

  it('does not run past the last sentence', async () => {
    const fetched: number[] = [];
    const prefetcher = new AudioPrefetcher(async (i) => (fetched.push(i), blob('x')), 3, 5);
    await prefetcher.get(1);
    await new Promise((r) => setTimeout(r, 0));
    expect(fetched.sort()).toEqual([1, 2]);
  });

  it('reuses an in-flight/finished fetch instead of requesting twice', async () => {
    const fetch = vi.fn(async () => blob('x'));
    const prefetcher = new AudioPrefetcher(fetch, 10, 1);
    await prefetcher.get(0); // also warms 1
    await prefetcher.get(1);
    expect(fetch).toHaveBeenCalledTimes(3); // 0, 1, then 2 warmed by get(1)
  });

  it('revokes URLs of sentences left behind', async () => {
    const prefetcher = new AudioPrefetcher(async () => blob('x'), 10, 1);
    await prefetcher.get(0);
    await prefetcher.get(1);
    await prefetcher.get(2);
    expect(revoked.length).toBeGreaterThanOrEqual(2); // 0 and 1 released
    expect(prefetcher.size).toBeLessThanOrEqual(3);
  });

  it('prunes entries outside the window after a seek', async () => {
    const signals = new Map<number, AbortSignal>();
    const prefetcher = new AudioPrefetcher(async (i, signal) => (signals.set(i, signal), blob('x')), 20, 2);
    await prefetcher.get(0);
    await new Promise((r) => setTimeout(r, 0));
    await prefetcher.get(10); // seek far ahead
    expect(signals.get(1)?.aborted).toBe(true);
    expect(signals.get(2)?.aborted).toBe(true);
    expect(prefetcher.readyAhead(10)).toBeLessThanOrEqual(2);
  });

  it('reports how many upcoming sentences are ready', async () => {
    const prefetcher = new AudioPrefetcher(async () => blob('x'), 10, 2);
    await prefetcher.get(0);
    await new Promise((r) => setTimeout(r, 0));
    expect(prefetcher.readyAhead(0)).toBe(2);
  });

  it('reset aborts in-flight requests and revokes finished ones', async () => {
    const signals: AbortSignal[] = [];
    const prefetcher = new AudioPrefetcher(
      (_i, signal) => {
        signals.push(signal);
        return new Promise<Blob>(() => undefined); // never resolves: a slow request
      },
      10,
      1,
    );
    void prefetcher.get(0).catch(() => undefined);
    prefetcher.reset();
    expect(signals.every((s) => s.aborted)).toBe(true);
    expect(prefetcher.size).toBe(0);
  });

  it('retries a transient server error once', async () => {
    const fetch = vi.fn().mockRejectedValueOnce(new ApiError(500, 'boom')).mockResolvedValue(blob('x'));
    const prefetcher = new AudioPrefetcher(fetch, 1, 0);
    await expect(prefetcher.get(0)).resolves.toMatch(/^blob:/);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('does not retry quota or connection errors', async () => {
    const quota = vi.fn().mockRejectedValue(new ApiError(429, 'limit'));
    await expect(new AudioPrefetcher(quota, 1, 0).get(0)).rejects.toMatchObject({ status: 429 });
    expect(quota).toHaveBeenCalledTimes(1);

    const offline = vi.fn().mockRejectedValue(new ApiError(0, 'offline'));
    await expect(new AudioPrefetcher(offline, 1, 0).get(0)).rejects.toMatchObject({ status: 0 });
    expect(offline).toHaveBeenCalledTimes(1);
  });

  it('allows retrying a sentence after it failed', async () => {
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(500, 'a'))
      .mockRejectedValueOnce(new ApiError(500, 'b'))
      .mockResolvedValue(blob('x'));
    const prefetcher = new AudioPrefetcher(fetch, 1, 0);
    await expect(prefetcher.get(0)).rejects.toBeInstanceOf(ApiError);
    await expect(prefetcher.get(0)).resolves.toMatch(/^blob:/);
  });
});
