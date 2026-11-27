export interface Book {
  id: number;
  title: string;
  author: string;
  total_chapters: number;
  total_sentences: number;
  total_words: number;
  created_at: string | null;
  /** A system book shared with everyone. */
  is_public?: boolean;
  /** False for a public book that someone else uploaded. */
  is_mine?: boolean;
  /** On the signed-in user's shelf (own books always are; a public book only after "Thêm vào kệ"). */
  on_shelf?: boolean;
  category?: Category | null;
  /** Relative URL of the cover image, readable without a token. */
  cover_url?: string | null;
  /** The signed-in user's progress; null when they never opened the book. */
  progress?: Progress | null;
}

export interface Category {
  id: number;
  name: string;
  slug: string;
  icon: string;
  color: string;
}

export type ReadStatus = 'unread' | 'reading' | 'completed';

export interface Progress {
  status: ReadStatus;
  is_favorite: boolean;
  current_chapter: number;
  current_sentence_index: number;
  completion_percentage: number;
  last_read_at: string | null;
  voice: string | null;
}

export interface ShelfCounts {
  unread: number;
  reading: number;
  completed: number;
  favorite: number;
}

export interface BookSentence {
  sentence_index: number;
  chapter_index: number;
  text_content: string;
  word_count: number;
}

export interface BookUploadResponse {
  status: string;
  book_id: number;
  title: string;
  total_chapters: number;
  total_sentences: number;
  total_words: number;
}

/** Kept as a name for "a book as the signed-in user sees it": every Book already carries its progress. */
export type BookWithProgress = Book;

/** One entry of the table of contents (GET /api/books/{id}/chapters). Sentence indexes are inclusive. */
export interface Chapter {
  chapter_index: number;
  title: string;
  start_sentence_index: number;
  end_sentence_index: number;
  sentence_count: number;
  word_count: number;
}
