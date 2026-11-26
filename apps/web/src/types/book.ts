export interface Book {
  id: number;
  title: string;
  author: string;
  total_chapters: number;
  total_sentences: number;
  total_words: number;
  created_at: string | null;
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

/** A book together with its reading progress (for the library). */
export interface BookWithProgress extends Book {
  bookmark: import('./player.ts').Bookmark | null;
}
