import React, { useMemo, useState } from 'react';
import { Globe, Lock, Pencil, Plus, Trash2 } from 'lucide-react';
import { listSystemBooks, setBookPublic } from '../../api/adminApi.ts';
import { deleteBook } from '../../api/booksApi.ts';
import { useApp } from '../../context/AppContext.tsx';
import { useAsyncData } from '../../hooks/useAsyncData.ts';
import { sortSystemBooks } from '../../lib/admin.ts';
import { AdminBook } from '../../types/admin.ts';
import { Book } from '../../types/book.ts';
import { EditBookDialog } from '../Dialogs/EditBookDialog.tsx';
import { UploadDialog } from '../Dialogs/UploadDialog.tsx';
import { BookCover } from '../Library/BookCover.tsx';
import { ConfirmDialog } from '../common/ConfirmDialog.tsx';
import { EmptyState, ErrorState, LoadingState } from '../common/StateViews.tsx';

/** The edit dialog works on a Book; the admin list only has the fields it needs. */
const asBook = (b: AdminBook): Book => ({
  id: b.id, title: b.title, author: b.author, total_chapters: b.total_chapters, total_sentences: 0, total_words: 0,
  created_at: null, is_public: b.is_public, category: b.category, cover_url: b.cover_url,
});

/** Quản trị › Sách hệ thống: add, edit, delete, publish and unpublish the books shared with everyone. */
export const SystemBooksPanel: React.FC<{ active: boolean }> = ({ active }) => {
  const { toast, showError } = useApp();
  const books = useAsyncData(listSystemBooks, [], active);
  const [pending, setPending] = useState<AdminBook | null>(null);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<AdminBook | null>(null);
  const [toDelete, setToDelete] = useState<AdminBook | null>(null);
  const sorted = useMemo(() => sortSystemBooks(books.data ?? []), [books.data]);

  const change = async (book: AdminBook, isPublic: boolean) => {
    try {
      await setBookPublic(book.id, isPublic);
      toast(isPublic ? `Đã công khai "${book.title}"` : `Đã gỡ "${book.title}" khỏi Khám phá`);
      books.reload();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Không đổi được trạng thái sách.');
    }
  };

  const remove = async () => {
    const target = toDelete;
    setToDelete(null);
    if (!target) return;
    try {
      await deleteBook(target.id);
      toast(`Đã xóa "${target.title}".`);
      books.reload();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Không xóa được sách.');
    }
  };

  if (!books.data && !books.error) return <LoadingState />; // also before the first request starts (the screen is hidden until opened)
  if (books.error) return <ErrorState message={books.error} onRetry={books.reload} />;

  return (
    <>
      <div className="panel-bar">
        <p className="muted">Sách công khai hiện ở trang Khám Phá của mọi người. Bạn chỉ công khai, sửa và xóa được sách do chính bạn tải lên hoặc sách đã công khai.</p>
        <button className="btn-primary" onClick={() => setAdding(true)}><Plus size={16} /> Thêm sách hệ thống</button>
      </div>
      {sorted.length === 0 ? (
        <EmptyState title="Chưa có sách hệ thống nào." hint="Dùng “Thêm sách hệ thống” để đăng cuốn đầu tiên." />
      ) : (
        <ul className="studio-list">
          {sorted.map((book) => (
            <li key={book.id} className="studio-row">
              <div className="admin-cover"><BookCover title={book.title} url={book.cover_url} /></div>
              <div className="studio-info">
                <span className="studio-name">{book.title}</span>
                <span className="muted">{book.author || 'Không rõ tác giả'} · {book.total_chapters} chương{book.category ? ` · ${book.category.name}` : ''}</span>
                <span className="chip-row">
                  {book.is_public ? <span className="chip static selected"><Globe size={12} /> Công khai · {book.shelf_count} kệ</span> : <span className="chip static"><Lock size={12} /> Riêng tư</span>}
                </span>
              </div>
              <span className="row-actions">
                {book.is_public ? (
                  <button className="btn-secondary small" onClick={() => setPending(book)}>Gỡ công khai</button>
                ) : (
                  <button className="btn-primary small" disabled={!book.is_mine} onClick={() => change(book, true)}>Công khai</button>
                )}
                <button className="btn-ghost small" aria-label={`Sửa sách ${book.title}`} onClick={() => setEditing(book)}><Pencil size={14} /></button>
                <button className="btn-danger small" aria-label={`Xóa sách ${book.title}`} onClick={() => setToDelete(book)}><Trash2 size={14} /></button>
              </span>
            </li>
          ))}
        </ul>
      )}

      {adding && (
        <UploadDialog
          defaultPublic
          onClose={() => setAdding(false)}
          onUploaded={(result) => {
            setAdding(false);
            toast(`Đã thêm "${result.title}"`);
            books.reload();
          }}
        />
      )}
      {editing && (
        <EditBookDialog
          book={asBook(editing)}
          onClose={() => setEditing(null)}
          onSaved={(saved) => {
            setEditing(null);
            toast(`Đã lưu "${saved.title}"`);
            books.reload();
          }}
        />
      )}
      {pending && (
        <ConfirmDialog
          title="Gỡ công khai"
          message={`Gỡ "${pending.title}" khỏi Khám Phá? ${pending.shelf_count > 0 ? `${pending.shelf_count} người đang để sách này trên kệ sẽ không còn thấy nó nữa.` : ''}`}
          confirmLabel="Gỡ"
          danger
          onConfirm={() => { const book = pending; setPending(null); void change(book, false); }}
          onCancel={() => setPending(null)}
        />
      )}
      {toDelete && (
        <ConfirmDialog
          title="Xóa sách"
          message={`Xóa hẳn "${toDelete.title}"? ${toDelete.shelf_count > 0 ? `${toDelete.shelf_count} người đang giữ sách này sẽ mất sách cùng tiến độ nghe và trích dẫn của họ. ` : ''}Việc này không thể hoàn tác.`}
          confirmLabel="Xóa"
          danger
          onConfirm={() => void remove()}
          onCancel={() => setToDelete(null)}
        />
      )}
    </>
  );
};
