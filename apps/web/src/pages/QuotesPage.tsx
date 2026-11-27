import React, { useMemo, useState } from 'react';
import { ListMusic, Search, Square, SkipBack, SkipForward } from 'lucide-react';
import { deleteNote, listNotes } from '../api/notesApi.ts';
import { ConfirmDialog } from '../components/common/ConfirmDialog.tsx';
import { EmotionChips } from '../components/common/EmotionChips.tsx';
import { PageHeader } from '../components/common/PageHeader.tsx';
import { EmptyState, ErrorState, LoadingState } from '../components/common/StateViews.tsx';
import { NoteDialog } from '../components/Dialogs/NoteDialog.tsx';
import { QuoteCard } from '../components/Library/QuoteCard.tsx';
import { useApp } from '../context/AppContext.tsx';
import { useAsyncData } from '../hooks/useAsyncData.ts';
import { useQuotePlaylist } from '../hooks/useQuotePlaylist.ts';
import { LibraryData } from '../hooks/useLibrary.ts';
import { matchesQuote, playlistProgress } from '../lib/quotes.ts';
import { EmotionTag, Note } from '../types/note.ts';
import { PAUSE_EVENT } from './ReaderPage.tsx';

interface QuotesPageProps {
  active: boolean;
  library: LibraryData;
  /** Show only the quotes of this book (set from a book card). */
  bookId: number | null;
  onBookChange: (bookId: number | null) => void;
}

/** S06 – Trích dẫn yêu thích: every saved passage, filtered by book or feeling, with a play-all mode. */
export const QuotesPage: React.FC<QuotesPageProps> = ({ active, library, bookId, onBookChange }) => {
  const { openInReader, showError, toast } = useApp();
  const [tag, setTag] = useState<EmotionTag | null>(null);
  const [query, setQuery] = useState('');
  const [toEdit, setToEdit] = useState<Note | null>(null);
  const [toDelete, setToDelete] = useState<Note | null>(null);
  const playlist = useQuotePlaylist(showError);
  const quotes = useAsyncData(() => listNotes({ bookId, emotionTag: tag }), [bookId, tag, library.version], active);
  const shown = useMemo(() => (quotes.data ?? []).filter((n) => matchesQuote(n, query)), [quotes.data, query]);

  const playAll = (from = 0) => {
    window.dispatchEvent(new Event(PAUSE_EVENT)); // never overlap with the reader
    playlist.start(shown, from);
  };

  const remove = async () => {
    if (!toDelete) return;
    const target = toDelete;
    setToDelete(null);
    try {
      await deleteNote(target.id);
      toast('Đã xóa trích dẫn.');
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Không xóa được trích dẫn.');
    }
    void library.reload();
  };

  const filtered = tag !== null || bookId !== null || !!query.trim();

  return (
    <div className="quotes-page">
      <PageHeader title="Trích dẫn yêu thích" subtitle="Những đoạn hay bạn đã đánh dấu khi nghe, kèm âm thanh lưu sẵn.">
        {playlist.playing ? (
          <div className="playlist-bar" role="group" aria-label="Phát liên tục">
            <span className="muted">Đang phát {playlistProgress(playlist.index, playlist.queue.length)}</span>
            <button className="btn-ghost icon" onClick={playlist.previous} aria-label="Trích dẫn trước"><SkipBack size={16} /></button>
            <button className="btn-secondary small" onClick={playlist.stop}><Square size={14} /> Dừng</button>
            <button className="btn-ghost icon" onClick={playlist.next} aria-label="Trích dẫn kế tiếp"><SkipForward size={16} /></button>
          </div>
        ) : (
          <button className="btn-primary" onClick={() => playAll()} disabled={shown.length === 0}><ListMusic size={16} /> Phát liên tục{shown.length > 0 && ` (${shown.length})`}</button>
        )}
      </PageHeader>

      <div className="library-toolbar">
        <div className="search-box">
          <Search size={16} className="search-icon" aria-hidden="true" />
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Tìm trong trích dẫn…" aria-label="Tìm trích dẫn" />
        </div>
        <select value={bookId ?? ''} onChange={(e) => onBookChange(e.target.value ? Number(e.target.value) : null)} aria-label="Lọc theo sách">
          <option value="">Tất cả sách</option>
          {library.books.map((b) => <option key={b.id} value={b.id}>{b.title}</option>)}
        </select>
      </div>
      <EmotionChips value={tag} onChange={setTag} allLabel="Tất cả cảm xúc" />

      {quotes.loading && !quotes.data && <LoadingState />}
      {quotes.error && <ErrorState message={quotes.error} onRetry={quotes.reload} />}
      {quotes.data && shown.length === 0 && (
        <EmptyState
          title={filtered ? 'Không có trích dẫn phù hợp.' : 'Chưa có trích dẫn nào.'}
          hint={filtered ? 'Thử bỏ bớt bộ lọc.' : 'Khi nghe một đoạn hay, bấm “Đánh dấu đoạn này” (phím B) trong Phòng Đọc.'}
        />
      )}
      <div className="quotes-list">
        {shown.map((note, position) => (
          <QuoteCard
            key={note.id}
            note={note}
            playing={playlist.current?.id === note.id}
            onPlay={() => (playlist.current?.id === note.id ? playlist.stop() : playAll(position))}
            onGo={() => openInReader(note.book_id, note.book_title, note.sentence_index)}
            onEdit={() => setToEdit(note)}
            onDelete={() => setToDelete(note)}
          />
        ))}
      </div>

      {toEdit && <NoteDialog mode="edit" note={toEdit} onClose={() => setToEdit(null)} onSaved={() => (setToEdit(null), void library.reload())} />}
      {toDelete && <ConfirmDialog title="Xóa trích dẫn" message="Xóa trích dẫn này và file âm thanh đã lưu của nó?" confirmLabel="Xóa" danger onConfirm={remove} onCancel={() => setToDelete(null)} />}
    </div>
  );
};
