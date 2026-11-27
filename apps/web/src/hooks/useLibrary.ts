import { useCallback, useEffect, useRef, useState } from 'react';
import { listBooks } from '../api/booksApi.ts';
import { BookWithProgress } from '../types/book.ts';

export interface LibraryData {
  /** The whole shelf, unfiltered (used for "resume the book you were reading"). */
  books: BookWithProgress[];
  loading: boolean;
  error: string | null;
  loaded: boolean;
  /** Changes on every reload: screens that fetch their own filtered lists reload when it changes. */
  version: number;
  reload: () => Promise<BookWithProgress[]>;
}

/** The user's shelf (each book already carries its progress). Shared by the library, quotes and the startup resume. */
export function useLibrary(): LibraryData {
  const [books, setBooks] = useState<BookWithProgress[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [version, setVersion] = useState(0);
  const latest = useRef(0);

  const reload = useCallback(async (): Promise<BookWithProgress[]> => {
    const id = ++latest.current;
    setLoading(true);
    setError(null);
    try {
      const shelf = await listBooks();
      if (id === latest.current) {
        setBooks(shelf);
        setLoaded(true);
        setVersion((v) => v + 1);
      }
      return shelf;
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

  return { books, loading, error, loaded, version, reload };
}
