import React, { useMemo, useState } from 'react';
import { Plus, Search } from 'lucide-react';
import { deleteBook } from '../api/booksApi.ts';
import { deleteNote, fetchNoteAudio } from '../api/notesApi.ts';
import { ConfirmDialog } from '../components/common/ConfirmDialog.tsx';
import { EmptyState, ErrorState, LoadingState } from '../components/common/StateViews.tsx';
import { ExportDialog } from '../components/Dialogs/ExportDialog.tsx';
import { NoteDialog } from '../components/Dialogs/NoteDialog.tsx';
import { UploadDialog } from '../components/Dialogs/UploadDialog.tsx';
import { BookCard } from '../components/Library/BookCard.tsx';
import { NoteCard } from '../components/Library/NoteCard.tsx';
import { useApp } from '../context/AppContext.tsx';
import { useBlobAudio } from '../hooks/useBlobAudio.ts';
import { LibraryData } from '../hooks/useLibrary.ts';
import { SORT_OPTIONS, SortOption, filterAndSortBooks } from '../lib/books.ts';
import { formatNumber, normalizeText } from '../lib/format.ts';
import { BookWithProgress } from '../types/book.ts';
import { Note } from '../types/note.ts';
import { PAUSE_EVENT } from './ReaderPage.tsx';

const ALL_BOOKS = 0;

interface LibraryPageProps {
  library: LibraryData;
}

/** S01 – Thư viện tài liệu and S06 – Ghi chú âm thanh. */
export const LibraryPage: React.FC<LibraryPageProps> = ({ library }) => {
  const { openInReader, toast, showError } = useApp();
  const [view, setView] = useState<'books' | 'notes'>('books');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<SortOption>(SORT_OPTIONS[0]);
  const [noteBook, setNoteBook] = useState<number>(ALL_BOOKS);
  const [uploading, setUploading] = useState(false);
  const [exporting, setExporting] = useState<BookWithProgress | null>(null);
  const [bookToDelete, setBookToDelete] = useState<BookWithProgress | null>(null);
  const [noteToDelete, setNoteToDelete] = useState<Note | null>(null);
  const [noteToEdit, setNoteToEdit] = useState<Note | null>(null);
  const { playBlob } = useBlobAudio();

  const books = useMemo(() => filterAndSortBooks(library.books, query, sort), [library.books, query, sort]);
  const notes = useMemo(() => {
    const needle = normalizeText(query.trim());
    return library.notes.filter(
      (n) => (noteBook === ALL_BOOKS || n.book_id === noteBook) && normalizeText(`${n.excerpt} ${n.note_text}`).includes(needle),
    );
  }, [library.notes, query, noteBook]);

  const switchView = (next: 'books' | 'notes') => {
    setView(next);
    setQuery('');
  };

  const confirmDeleteBook = async () => {
    if (!bookToDelete) return;
    try {
      await deleteBook(bookToDelete.id);
      toast(`Đã xóa "${bookToDelete.title}".`);
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Không xóa được tài liệu.');
    }
    setBookToDelete(null);
    void library.reload();
  };

  const confirmDeleteNote = async () => {
    if (!noteToDelete) return;
    try {
      await deleteNote(noteToDelete.id);
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Không xóa được ghi chú.');
    }
    setNoteToDelete(null);
    void library.reload();
  };

  const playNote = async (note: Note) => {
    window.dispatchEvent(new Event(PAUSE_EVENT)); // never overlap with the reader
    try {
      await playBlob(await fetchNoteAudio(note.id));
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Không phát được ghi chú.');
    }
  };

  return (
    <div className="library-page">
      <div className="segmented center" role="tablist" aria-label="Thư viện">
        <button role="tab" aria-selected={view === 'books'} className={view === 'books' ? 'active' : ''} onClick={() => switchView('books')}>Tài liệu</button>
        <button role="tab" aria-selected={view === 'notes'} className={view === 'notes' ? 'active' : ''} onClick={() => switchView('notes')}>Ghi chú</button>
      </div>

      <div className="library-toolbar">
        <div className="search-box">
          <Search size={16} className="search-icon" aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={view === 'books' ? 'Tìm theo tên…' : 'Tìm trong ghi chú…'}
            aria-label={view === 'books' ? 'Tìm tài liệu' : 'Tìm ghi chú'}
          />
        </div>
        {view === 'books' ? (
          <>
            <select value={sort} onChange={(e) => setSort(e.target.value as SortOption)} aria-label="Sắp xếp">
              {SORT_OPTIONS.map((o) => <option key={o}>{o}</option>)}
            </select>
            <button className="btn-primary" onClick={() => setUploading(true)}><Plus size={16} /> Thêm tài liệu</button>
          </>
        ) : (
          <select value={noteBook} onChange={(e) => setNoteBook(Number(e.target.value))} aria-label="Lọc theo tài liệu">
            <option value={ALL_BOOKS}>Tất cả</option>
            {library.books.map((b) => <option key={b.id} value={b.id}>{b.title}</option>)}
          </select>
        )}
      </div>

      {library.loading && !library.loaded && <LoadingState />}
      {library.error && <ErrorState message={library.error} onRetry={() => void library.reload()} />}

      {library.loaded && view === 'books' && (
        library.books.length === 0 ? (
          <EmptyState title="Chưa có tài liệu nào." hint="Bấm “Thêm tài liệu” để bắt đầu.">
            <button className="btn-primary" onClick={() => setUploading(true)}><Plus size={16} /> Thêm tài liệu</button>
          </EmptyState>
        ) : books.length === 0 ? (
          <EmptyState title="Không tìm thấy tài liệu phù hợp." />
        ) : (
          <div className="books-grid">
            {books.map((book) => (
              <BookCard
                key={book.id}
                book={book}
                onRead={() => openInReader(book.id, book.title)}
                onNotes={() => (setNoteBook(book.id), switchView('notes'))}
                onExport={() => setExporting(book)}
                onDelete={() => setBookToDelete(book)}
              />
            ))}
          </div>
        )
      )}

      {library.loaded && view === 'notes' && (
        library.notes.length === 0 ? (
          <EmptyState title="Chưa có ghi chú." hint="Hãy bôi đen một đoạn trong Phòng Đọc để tạo." />
        ) : notes.length === 0 ? (
          <EmptyState title="Không có ghi chú phù hợp." />
        ) : (
          <div className="notes-list">
            {notes.map((note) => (
              <NoteCard
                key={note.id}
                note={note}
                onPlay={() => playNote(note)}
                onGo={() => openInReader(note.book_id, note.book_title, note.sentence_index)}
                onEdit={() => setNoteToEdit(note)}
                onDelete={() => setNoteToDelete(note)}
              />
            ))}
          </div>
        )
      )}

      {uploading && (
        <UploadDialog
          onClose={() => setUploading(false)}
          onUploaded={(result) => {
            setUploading(false);
            toast(`Đã thêm "${result.title}" (${formatNumber(result.total_sentences)} câu)`);
            void library.reload();
          }}
        />
      )}
      {exporting && <ExportDialog book={exporting} onClose={() => setExporting(null)} />}
      {noteToEdit && (
        <NoteDialog mode="edit" note={noteToEdit} onClose={() => setNoteToEdit(null)} onSaved={() => (setNoteToEdit(null), void library.reload())} />
      )}
      {bookToDelete && (
        <ConfirmDialog
          title="Xóa tài liệu"
          message={`Xóa "${bookToDelete.title}"? Ghi chú và lịch sử đọc của tài liệu cũng bị xóa.`}
          confirmLabel="Xóa"
          danger
          onConfirm={confirmDeleteBook}
          onCancel={() => setBookToDelete(null)}
        />
      )}
      {noteToDelete && (
        <ConfirmDialog title="Xóa ghi chú" message="Xóa ghi chú này?" confirmLabel="Xóa" danger onConfirm={confirmDeleteNote} onCancel={() => setNoteToDelete(null)} />
      )}
    </div>
  );
};
