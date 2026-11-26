import { useCallback, useEffect, useRef, useState } from 'react';
import { listBooks } from '../api/booksApi.ts';
import { listNotes } from '../api/notesApi.ts';
import { fetchBookmark } from '../api/playerApi.ts';
import { BookWithProgress } from '../types/book.ts';
import { Note } from '../types/note.ts';

export interface LibraryData {
  books: BookWithProgress[];
  notes: Note[];
  loading: boolean;
  error: string | null;
  loaded: boolean;
  reload: () => Promise<BookWithProgress[]>;
}

/** Books with their reading progress, plus all notes. Shared by the library and the startup resume. */
export function useLibrary(): LibraryData {
  const [books, setBooks] = useState<BookWithProgress[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const latest = useRef(0);

  const reload = useCallback(async (): Promise<BookWithProgress[]> => {
    const id = ++latest.current;
    setLoading(true);
    setError(null);
    try {
      const [plain, allNotes] = await Promise.all([listBooks(), listNotes()]);
      const withProgress = await Promise.all(
        plain.map(async (book) => ({ ...book, bookmark: await fetchBookmark(book.id).catch(() => null) })),
      );
      if (id === latest.current) {
        setBooks(withProgress);
        setNotes(allNotes);
        setLoaded(true);
      }
      return withProgress;
    } catch (err) {
      if (id === latest.current) setError(err instanceof Error ? err.message : 'Không tải được thư viện.');
      return [];
    } finally {
      if (id === latest.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { books, notes, loading, error, loaded, reload };
}
