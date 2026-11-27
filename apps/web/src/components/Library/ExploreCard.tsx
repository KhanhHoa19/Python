import React from 'react';
import { Check, Plus } from 'lucide-react';
import { formatNumber } from '../../lib/format.ts';
import { BookWithProgress } from '../../types/book.ts';
import { BookCover } from './BookCover.tsx';

interface ExploreCardProps {
  book: BookWithProgress;
  busy: boolean;
  onAdd: () => void;
  onListen: () => void;
}

/** A public book in "Khám phá": add it to the shelf, or open it straight away. */
export const ExploreCard: React.FC<ExploreCardProps> = ({ book, busy, onAdd, onListen }) => {
  const author = book.author && book.author !== 'Unknown' ? book.author : '';
  return (
    <article className="book-card">
      <div className="cover-wrap"><BookCover title={book.title} url={book.cover_url} /></div>
      <div className="book-card-body">
        {book.category && <span className="category-chip">{book.category.name}</span>}
        <h3 className="book-card-title" title={book.title}>{book.title}</h3>
        <p className="book-card-author">{author || 'Sách hệ thống'}</p>
        <p className="book-card-meta">{formatNumber(book.total_chapters)} chương · {formatNumber(book.total_words)} từ</p>
        <div className="card-actions">
          <button className="btn-primary" onClick={onListen}>Nghe ngay</button>
          {book.on_shelf ? (
            <span className="shelf-state" title="Đã có trong kệ của bạn"><Check size={15} /> Trong kệ</span>
          ) : (
            <button className="btn-secondary small" onClick={onAdd} disabled={busy}><Plus size={15} /> Thêm vào kệ</button>
          )}
        </div>
      </div>
    </article>
  );
};
