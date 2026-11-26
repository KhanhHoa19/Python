import React from 'react';
import { Download, NotebookText, Trash2 } from 'lucide-react';
import { formatDateTime, formatNumber } from '../../lib/format.ts';
import { progressFraction } from '../../lib/books.ts';
import { BookWithProgress } from '../../types/book.ts';

interface BookCardProps {
  book: BookWithProgress;
  onRead: () => void;
  onNotes: () => void;
  onExport: () => void;
  onDelete: () => void;
}

export const BookCard: React.FC<BookCardProps> = ({ book, onRead, onNotes, onExport, onDelete }) => {
  const fraction = progressFraction(book);
  const started = fraction > 0;
  const author = book.author && book.author !== 'Unknown' ? ` · ${book.author}` : '';
  return (
    <article className="book-card">
      <h3 className="book-card-title">{book.title}</h3>
      <p className="book-card-author">{formatNumber(book.total_sentences)} câu · {formatNumber(book.total_words)} từ{author}</p>
      <div className="progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(fraction * 100)} aria-label={`Tiến độ ${book.title}`}>
        <div className="progress-fill" style={{ width: `${fraction * 100}%` }} />
      </div>
      <p className="book-card-meta">{Math.round(fraction * 100)}% · {started ? `Đọc: ${formatDateTime(book.bookmark?.last_read_at)}` : 'Chưa đọc'}</p>
      <div className="card-actions">
        <button className="btn-primary" onClick={onRead}>{started ? 'Tiếp tục đọc' : 'Bắt đầu đọc'}</button>
        <button className="btn-secondary icon" onClick={onNotes} aria-label={`Ghi chú của ${book.title}`} title="Ghi chú"><NotebookText size={16} /></button>
        <button className="btn-secondary icon" onClick={onExport} aria-label={`Xuất audio ${book.title}`} title="Xuất audio"><Download size={16} /></button>
        <button className="btn-danger icon" onClick={onDelete} aria-label={`Xóa ${book.title}`} title="Xóa"><Trash2 size={16} /></button>
      </div>
    </article>
  );
};
