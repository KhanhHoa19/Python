/**
 * Bounded look-ahead buffer of sentence audio.
 *
 * `get(i)` resolves to an object URL for sentence i and keeps fetching the next `ahead` sentences
 * in the background. Sentences behind the current one are released (object URLs revoked),
 * and `reset()` aborts everything in flight, so a seek can never play stale audio.
 */

import { ApiError } from '../api/client.ts';

export type FetchAudio = (index: number, signal: AbortSignal) => Promise<Blob>;

interface Entry {
  promise: Promise<string>;
  controller: AbortController;
  url: string | null;
}

export class AudioPrefetcher {
  private entries = new Map<number, Entry>();

  constructor(
    private readonly fetchAudio: FetchAudio,
    private readonly total: number,
    private ahead: number,
  ) {}

  setAhead(ahead: number): void {
    this.ahead = Math.max(0, ahead);
  }

  get size(): number {
    return this.entries.size;
  }

  /** Object URL for sentence `index`; also schedules the following `ahead` sentences. */
  get(index: number): Promise<string> {
    this.prune(index);
    const promise = this.load(index);
    for (let next = index + 1; next <= index + this.ahead && next < this.total; next++) {
      this.load(next).catch(() => undefined); // errors surface when that sentence is actually requested
    }
    return promise;
  }

  /** Start fetching `index..index+ahead` without waiting (used after a sentence starts playing). */
  warm(index: number): void {
    for (let next = index; next <= index + this.ahead && next < this.total; next++) {
      this.load(next).catch(() => undefined);
    }
  }

  /** Drop and revoke every sentence before `index`. */
  release(index: number): void {
    for (const [key, entry] of this.entries) {
      if (key < index) this.drop(key, entry);
    }
  }

  /** Drop everything outside the window [index, index + ahead] (after a seek, or once played). */
  prune(index: number): void {
    for (const [key, entry] of this.entries) {
      if (key < index || key > index + this.ahead) this.drop(key, entry);
    }
  }

  /** How many of the next `ahead` sentences after `index` are already downloaded. */
  readyAhead(index: number): number {
    let ready = 0;
    for (let next = index + 1; next <= index + this.ahead && next < this.total; next++) {
      if (this.entries.get(next)?.url) ready++;
    }
    return ready;
  }

  reset(): void {
    for (const [key, entry] of this.entries) this.drop(key, entry);
  }

  private drop(key: number, entry: Entry): void {
    entry.controller.abort();
    if (entry.url) URL.revokeObjectURL(entry.url);
    this.entries.delete(key);
  }

  private load(index: number): Promise<string> {
    const existing = this.entries.get(index);
    if (existing) return existing.promise;

    const controller = new AbortController();
    const entry: Entry = { controller, url: null, promise: Promise.resolve('') };
    entry.promise = this.fetchWithRetry(index, controller.signal).then(
      (blob) => {
        if (controller.signal.aborted) throw new DOMException('Aborted', 'AbortError');
        entry.url = URL.createObjectURL(blob);
        return entry.url;
      },
      (error) => {
        if (this.entries.get(index) === entry) this.entries.delete(index); // allow a later retry
        throw error;
      },
    );
    this.entries.set(index, entry);
    return entry.promise;
  }

  /** One retry for transient server errors; quota and connection errors are final. */
  private async fetchWithRetry(index: number, signal: AbortSignal): Promise<Blob> {
    try {
      return await this.fetchAudio(index, signal);
    } catch (error) {
      if (error instanceof ApiError && (error.isQuotaError || error.isConnectionError)) throw error;
      if (signal.aborted || (error instanceof DOMException && error.name === 'AbortError')) throw error;
      return this.fetchAudio(index, signal);
    }
  }
}
