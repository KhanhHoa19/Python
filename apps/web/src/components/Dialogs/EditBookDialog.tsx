import React, { useRef, useState } from 'react';
import { ImagePlus } from 'lucide-react';
import { replaceCover, updateBook } from '../../api/booksApi.ts';
import { useApp } from '../../context/AppContext.tsx';
import { MAX_TITLE_LENGTH, checkBookTitle } from '../../lib/books.ts';
import { Book } from '../../types/book.ts';
import { Modal } from '../common/Modal.tsx';
import { BookCover } from '../Library/BookCover.tsx';

const MAX_COVER_BYTES = 2 * 1024 * 1024;

interface EditBookDialogProps {
  book: Book;
  onClose: () => void;
  onSaved: (book: Book) => void;
}

/** S01 – Sửa thông tin tài liệu: tên, tác giả, thể loại và ảnh bìa. */
export const EditBookDialog: React.FC<EditBookDialogProps> = ({ book, onClose, onSaved }) => {
  const { categories } = useApp();
  const [title, setTitle] = useState(book.title);
  const [author, setAuthor] = useState(book.author ?? '');
  const [categoryId, setCategoryId] = useState<number | null>(book.category?.id ?? null);
  const [cover, setCover] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const pickCover = (file: File | undefined) => {
    if (!file) return;
    if (!['image/jpeg', 'image/png'].includes(file.type)) return setError('Ảnh bìa phải là JPEG hoặc PNG.');
    if (file.size > MAX_COVER_BYTES) return setError('Ảnh bìa tối đa 2 MB.');
    setError(null);
    setCover(file);
    setPreview((old) => {
      if (old) URL.revokeObjectURL(old);
      return URL.createObjectURL(file);
    });
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const check = checkBookTitle(title);
    if (!check.ok) return setError(check.error);
    const changes: { title?: string; author?: string; category_id?: number | null } = {};
    if (check.title !== book.title) changes.title = check.title;
    if (author.trim() !== (book.author ?? '').trim()) changes.author = author.trim();
    if (categoryId !== (book.category?.id ?? null)) changes.category_id = categoryId;
    if (!cover && Object.keys(changes).length === 0) return onClose(); // nothing to change
    setBusy(true);
    setError(null);
    try {
      let saved = Object.keys(changes).length ? await updateBook(book.id, changes) : book;
      if (cover) saved = await replaceCover(book.id, cover);
      onSaved(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không lưu được.');
      setBusy(false);
    }
  };

  return (
    <Modal title="Sửa thông tin tài liệu" onClose={busy ? () => undefined : onClose} width={520}>
      <form className="modal-form" onSubmit={submit}>
        <div className="edit-book">
          <div className="edit-cover">
            <BookCover title={title || book.title} url={preview ?? book.cover_url} />
            <button type="button" className="btn-secondary small" onClick={() => fileRef.current?.click()}><ImagePlus size={15} /> Đổi ảnh bìa</button>
            <input ref={fileRef} type="file" accept="image/jpeg,image/png" hidden onChange={(e) => pickCover(e.target.files?.[0])} />
          </div>
          <div className="modal-form">
            <div className="form-group">
              <label htmlFor="edit-title">Tên tài liệu</label>
              <input id="edit-title" value={title} maxLength={MAX_TITLE_LENGTH * 2} onChange={(e) => (setTitle(e.target.value), setError(null))} autoFocus />
            </div>
            <div className="form-group">
              <label htmlFor="edit-author">Tác giả</label>
              <input id="edit-author" value={author} maxLength={MAX_TITLE_LENGTH} onChange={(e) => setAuthor(e.target.value)} />
            </div>
            <div className="form-group">
              <label htmlFor="edit-category">Thể loại</label>
              <select id="edit-category" value={categoryId ?? ''} onChange={(e) => setCategoryId(e.target.value ? Number(e.target.value) : null)}>
                <option value="">(Chưa phân loại)</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
          </div>
        </div>
        {error && <p className="status-text error" role="alert">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={onClose} disabled={busy}>Hủy</button>
          <button type="submit" className="btn-primary" disabled={busy || !title.trim()}>Lưu</button>
        </div>
      </form>
    </Modal>
  );
};
