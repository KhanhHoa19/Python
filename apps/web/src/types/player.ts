export interface Bookmark {
  book_id: number;
  current_chapter: number;
  current_sentence_index: number;
  completion_percentage: number;
  last_read_at: string | null;
}

export interface ReadingSessionPayload {
  book_id: number;
  duration_seconds: number;
  sentences_read: number;
  words_read: number;
  start_time: string;
  end_time: string;
}

export type PlayerState = 'idle' | 'loading' | 'playing' | 'paused' | 'finished';

export const SPEED_LEVELS = [0.75, 1.0, 1.25, 1.5] as const;
