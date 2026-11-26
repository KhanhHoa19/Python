import React from 'react';
import { listBooks } from '../../api/booksApi.ts';
import { useAsyncData } from '../../hooks/useAsyncData.ts';
import { formatNumber } from '../../lib/format.ts';
import { Book } from '../../types/book.ts';
import { Modal } from '../common/Modal.tsx';
import { EmptyState, ErrorState, LoadingState } from '../common/StateViews.tsx';

interface BookPickerDialogProps {
  onPick: (book: Book) => void;
  onClose: () => void;
}

/** "Đổi tài liệu" in the reader. */
export const BookPickerDialog: React.FC<BookPickerDialogProps> = ({ onPick, onClose }) => {
  const books = useAsyncData(() => listBooks(), []);
  return (
    <Modal title="Chọn tài liệu" onClose={onClose}>
      {books.loading && <LoadingState />}
      {books.error && <ErrorState message={books.error} onRetry={books.reload} />}
      {books.data && books.data.length === 0 && <EmptyState title="Chưa có tài liệu nào." hint="Hãy thêm ở tab Thư Viện." />}
      <ul className="picker-list">
        {books.data?.map((book) => (
          <li key={book.id}>
            <button className="picker-item" onClick={() => onPick(book)}>
              <span>{book.title}</span>
              <span className="muted">{formatNumber(book.total_sentences)} câu</span>
            </button>
          </li>
        ))}
      </ul>
    </Modal>
  );
};
