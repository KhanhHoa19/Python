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
}

export interface NoteCreatePayload {
  book_id: number;
  sentence_index: number;
  start_offset: number;
  end_offset: number;
  note_text: string;
}
