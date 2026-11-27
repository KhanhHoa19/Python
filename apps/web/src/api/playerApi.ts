import { apiGet, apiGetBlob, apiPost } from './client.ts';
import { Bookmark, ReadingSessionPayload } from '../types/player.ts';

export async function fetchBookmark(bookId: number): Promise<Bookmark> {
  return apiGet<Bookmark>(`/bookmarks/${bookId}`);
}

export async function saveBookmark(
  payload: { book_id: number; current_chapter: number; current_sentence_index: number; completion_percentage: number; voice?: string | null },
  keepalive = false,
): Promise<void> {
  await apiPost('/bookmarks', payload, { keepalive });
}

export async function recordReadingSession(payload: ReadingSessionPayload, keepalive = false): Promise<void> {
  await apiPost('/sessions', payload, { keepalive });
}

/** Audio for one sentence. Always requested at speed 1.0; playback speed is applied by the browser. */
export async function fetchSentenceAudio(
  bookId: number,
  sentenceIndex: number,
  voice?: string | null,
  signal?: AbortSignal,
  /** Multi-voice narration: the voice that reads the lines in quotation marks (the narrator is `voice`). */
  dialogueVoice?: string | null,
): Promise<Blob> {
  return apiGetBlob(
    `/audio/${bookId}/${sentenceIndex}`,
    { speed: 1.0, voice: voice ?? undefined, dialogue_voice: dialogueVoice || undefined },
    signal,
  );
}
