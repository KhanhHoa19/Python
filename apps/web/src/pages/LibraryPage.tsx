import React, { useEffect, useState } from 'react';
import { Plus, Search } from 'lucide-react';
import { deleteBook, fetchShelfCounts, listBooks, removeFromShelf, setFavorite, setReadStatus } from '../api/booksApi.ts';
import { ConfirmDialog } from '../components/common/ConfirmDialog.tsx';
import { CategoryChips } from '../components/common/CategoryChips.tsx';
import { PageHeader } from '../components/common/PageHeader.tsx';
import { EmptyState, ErrorState, LoadingState } from '../components/common/StateViews.tsx';
import { EditBookDialog } from '../components/Dialogs/EditBookDialog.tsx';
import { ExportDialog } from '../components/Dialogs/ExportDialog.tsx';
import { UploadDialog } from '../components/Dialogs/UploadDialog.tsx';
import { BookCard } from '../components/Library/BookCard.tsx';
import { useApp } from '../context/AppContext.tsx';
import { useAsyncData } from '../hooks/useAsyncData.ts';
import { useDebounced } from '../hooks/useDebounced.ts';
import { LibraryData } from '../hooks/useLibrary.ts';
import { formatNumber } from '../lib/format.ts';
import { SHELF_TABS, SORT_OPTIONS, SOURCE_OPTIONS, ShelfTab, SortValue, SourceValue, pickInitialTab } from '../lib/shelf.ts';
import { BookWithProgress } from '../types/book.ts';

interface LibraryPageProps {
  library: LibraryData;
  active: boolean;
}

/** S01 – Kệ sách của tôi: 4 tabs by reading status. */
export const LibraryPage: React.FC<LibraryPageProps> = ({ library, active }) => {
  const { openInReader, openQuotes, toast, showError, category, categories, setCategory } = useApp();
  const [tab, setTab] = useState<ShelfTab | null>(null); // null until the first counts decide which tab to open
  const [query, setQuery] = useState('');
  const [source, setSource] = useState<SourceValue>('all');
  const [sort, setSort] = useState<SortValue>('recent');
  const [uploading, setUploading] = useState(false);
  const [exporting, setExporting] = useState<BookWithProgress | null>(null);
  const [bookToEdit, setBookToEdit] = useState<BookWithProgress | null>(null);
  const [bookToDelete, setBookToDelete] = useState<BookWithProgress | null>(null);
  const debouncedQuery = useDebounced(query);

  // Open the first tab that has books (once, when the shelf is first shown).
  useEffect(() => {
    if (tab !== null || !active) return;
    let alive = true;
    void fetchShelfCounts()
      .then((counts) => alive && setTab(pickInitialTab(counts)))
      .catch(() => alive && setTab('reading'));
    return () => {
      alive = false;
    };
  }, [tab, active]);

  const filters = { q: debouncedQuery, category, source };
  const shelf = useAsyncData(
    () => Promise.all([listBooks({ ...filters, status: tab, sort }), fetchShelfCounts(filters)]),
    [debouncedQuery, category, source, sort, tab, library.version],
    active && tab !== null,
  );
  const [books, counts] = shelf.data ?? [[], null];

  const switchTab = (next: ShelfTab) => setTab(next);

  const refresh = () => void library.reload();

  const act = async (work: () => Promise<unknown>, success?: string) => {
    try {
      await work();
      if (success) toast(success);
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Không thực hiện được.');
    }
    refresh();
  };

  const removeBook = (book: BookWithProgress) => {
    if (book.is_mine === false) void act(() => removeFromShelf(book.id), `Đã gỡ "${book.title}" khỏi kệ.`);
    else setBookToDelete(book);
  };

  const confirmDeleteBook = async () => {
    if (!bookToDelete) return;
    const target = bookToDelete;
    setBookToDelete(null);
    await act(() => deleteBook(target.id), `Đã xóa "${target.title}".`);
  };

  const filtered = !!debouncedQuery.trim() || category !== null || source !== 'all';

  return (
    <div className="library-page">
      <PageHeader title="Kệ sách của tôi" subtitle="Sách của bạn và sách hệ thống bạn đã thêm, theo tiến độ nghe.">
        <button className="btn-primary" onClick={() => setUploading(true)}><Plus size={16} /> Thêm tài liệu</button>
      </PageHeader>

      <div className="segmented shelf-tabs" role="tablist" aria-label="Kệ sách">
        {SHELF_TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} className={tab === t.id ? 'active' : ''} onClick={() => switchTab(t.id)}>
            {t.label}{counts && <span className="tab-count">{counts[t.id]}</span>}
          </button>
        ))}
      </div>

      <CategoryChips categories={categories} selected={category} onSelect={setCategory} />

      <div className="library-toolbar">
        <div className="search-box">
          <Search size={16} className="search-icon" aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Tìm theo tên sách hoặc tác giả…"
            aria-label="Tìm sách"
          />
        </div>
        <select value={source} onChange={(e) => setSource(e.target.value as SourceValue)} aria-label="Nguồn sách">
          {SOURCE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value as SortValue)} aria-label="Sắp xếp">
          {SORT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>

      {(tab === null || (shelf.loading && !shelf.data)) && <LoadingState />}
      {shelf.error && <ErrorState message={shelf.error} onRetry={shelf.reload} />}

      {tab !== null && shelf.data && (
        books.length === 0 ? (
          filtered ? (
            <EmptyState title="Không tìm thấy sách phù hợp." hint="Thử bỏ bớt bộ lọc, hoặc đổi sang tab khác." />
          ) : tab === 'reading' && counts && counts.unread + counts.completed + counts.favorite > 0 ? (
            <EmptyState title="Bạn chưa nghe dở cuốn nào." hint="Mở tab “Chưa nghe” để bắt đầu một cuốn." />
          ) : (
            <EmptyState title="Chưa có sách nào ở đây." hint="Thêm tài liệu của bạn, hoặc vào “Khám phá” để chọn sách hệ thống.">
              <button className="btn-primary" onClick={() => setUploading(true)}><Plus size={16} /> Thêm tài liệu</button>
            </EmptyState>
          )
        ) : (
          <div className="books-grid">
            {books.map((book) => (
              <BookCard
                key={book.id}
                book={book}
                onRead={() => openInReader(book.id, book.title)}
                onEdit={() => setBookToEdit(book)}
                onNotes={() => openQuotes(book.id)}
                onExport={() => setExporting(book)}
                onFavorite={() => void act(() => setFavorite(book.id, !book.progress?.is_favorite))}
                onStatus={(status) => void act(() => setReadStatus(book.id, status), status === 'completed' ? `Đã đánh dấu "${book.title}" là nghe xong.` : `"${book.title}" sẽ nghe lại từ đầu.`)}
                onRemove={() => removeBook(book)}
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
            setTab('unread');
            refresh();
          }}
        />
      )}
      {bookToEdit && (
        <EditBookDialog
          book={bookToEdit}
          onClose={() => setBookToEdit(null)}
          onSaved={(saved) => {
            setBookToEdit(null);
            toast(`Đã lưu "${saved.title}".`);
            refresh();
          }}
        />
      )}
      {exporting && <ExportDialog book={exporting} onClose={() => setExporting(null)} />}
      {bookToDelete && (
        <ConfirmDialog
          title="Xóa tài liệu"
          message={`Xóa "${bookToDelete.title}"? Ghi chú, tiến độ và ảnh bìa của tài liệu cũng bị xóa.`}
          confirmLabel="Xóa"
          danger
          onConfirm={confirmDeleteBook}
          onCancel={() => setBookToDelete(null)}
        />
      )}
    </div>
  );
};
