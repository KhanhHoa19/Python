import React, { useState } from 'react';
import { Plus, Search } from 'lucide-react';
import { addToShelf, exploreBooks } from '../api/booksApi.ts';
import { CategoryChips } from '../components/common/CategoryChips.tsx';
import { PageHeader } from '../components/common/PageHeader.tsx';
import { EmptyState, ErrorState, LoadingState } from '../components/common/StateViews.tsx';
import { UploadDialog } from '../components/Dialogs/UploadDialog.tsx';
import { ExploreCard } from '../components/Library/ExploreCard.tsx';
import { useApp } from '../context/AppContext.tsx';
import { useAsyncData } from '../hooks/useAsyncData.ts';
import { useDebounced } from '../hooks/useDebounced.ts';
import { LibraryData } from '../hooks/useLibrary.ts';
import { BookWithProgress } from '../types/book.ts';

interface ExplorePageProps {
  active: boolean;
  library: LibraryData;
}

/** S10 – Khám phá: the public catalogue (system books). */
export const ExplorePage: React.FC<ExplorePageProps> = ({ active, library }) => {
  const { user, category, categories, setCategory, openInReader, toast, showError } = useApp();
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<'newest' | 'title'>('newest');
  const [busyId, setBusyId] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);
  const debounced = useDebounced(query);
  const catalogue = useAsyncData(() => exploreBooks({ q: debounced, category, sort }), [debounced, category, sort, library.version], active);
  const books = catalogue.data ?? [];

  const add = async (book: BookWithProgress, listen = false) => {
    setBusyId(book.id);
    try {
      if (!book.on_shelf) await addToShelf(book.id);
      if (listen) openInReader(book.id, book.title);
      else toast(`Đã thêm "${book.title}" vào kệ.`);
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Không thêm được vào kệ.');
    }
    setBusyId(null);
    await library.reload();
  };

  return (
    <div className="explore-page">
      <PageHeader title="Khám phá" subtitle="Kho sách chung của hệ thống. Thêm vào kệ để lưu tiến độ nghe riêng của bạn.">
        {user.role === 'admin' && <button className="btn-primary" onClick={() => setUploading(true)}><Plus size={16} /> Thêm sách hệ thống</button>}
      </PageHeader>

      <CategoryChips categories={categories} selected={category} onSelect={setCategory} />

      <div className="library-toolbar">
        <div className="search-box">
          <Search size={16} className="search-icon" aria-hidden="true" />
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Tìm theo tên sách hoặc tác giả…" aria-label="Tìm sách hệ thống" />
        </div>
        <select value={sort} onChange={(e) => setSort(e.target.value as 'newest' | 'title')} aria-label="Sắp xếp">
          <option value="newest">Mới nhất</option>
          <option value="title">Tên A→Z</option>
        </select>
      </div>

      {catalogue.loading && !catalogue.data && <LoadingState />}
      {catalogue.error && <ErrorState message={catalogue.error} onRetry={catalogue.reload} />}
      {catalogue.data && books.length === 0 && (
        <EmptyState
          title={debounced.trim() || category ? 'Không tìm thấy sách phù hợp.' : 'Chưa có sách hệ thống nào.'}
          hint={user.role === 'admin' ? 'Dùng “Thêm sách hệ thống” để đăng cuốn đầu tiên.' : 'Quản trị viên sẽ đăng sách mẫu ở đây.'}
        />
      )}
      {books.length > 0 && (
        <div className="books-grid">
          {books.map((book) => (
            <ExploreCard key={book.id} book={book} busy={busyId === book.id} onAdd={() => void add(book)} onListen={() => void add(book, true)} />
          ))}
        </div>
      )}

      {uploading && (
        <UploadDialog
          defaultPublic
          onClose={() => setUploading(false)}
          onUploaded={(result) => {
            setUploading(false);
            toast(`Đã đăng "${result.title}" vào Khám phá.`);
            void library.reload();
          }}
        />
      )}
    </div>
  );
};
