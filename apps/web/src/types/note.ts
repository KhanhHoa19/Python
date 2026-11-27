export type EmotionTag = 'inspiring' | 'touching' | 'wise' | 'funny';

/** A favourite quote ("Trích dẫn yêu thích"): a highlighted excerpt or a whole sentence. */
export interface Note {
  id: number;
  book_id: number;
  book_title: string;
  sentence_index: number;
  start_offset: number;
  end_offset: number;
  excerpt: string;
  note_text: string;
  created_at: string;
  emotion_tag: EmotionTag | null;
  /** The sentences just before and after, so the quote keeps its context. */
  context_before: string;
  context_after: string;
  /** A permanent copy of the audio is saved (it survives clearing the cache). */
  has_audio: boolean;
  voice: string | null;
}

/** Give both offsets for a highlighted part; give neither for the whole sentence (the one-tap bookmark). */
export interface NoteCreatePayload {
  book_id: number;
  sentence_index: number;
  start_offset?: number;
  end_offset?: number;
  note_text?: string;
  emotion_tag?: EmotionTag | null;
  voice?: string | null;
}
