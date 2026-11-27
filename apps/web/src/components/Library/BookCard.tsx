import React from 'react';
import { CheckCheck, Download, Heart, NotebookText, Pencil, RotateCcw, Trash2, Unplug } from 'lucide-react';
import { formatDateTime, formatNumber } from '../../lib/format.ts';
import { progressFraction } from '../../lib/books.ts';
import { playLabel } from '../../lib/shelf.ts';
import { BookWithProgress } from '../../types/book.ts';
import { BookCover } from './BookCover.tsx';

interface BookCardProps {
  book: BookWithProgress;
  onRead: () => void;
  onEdit: () => void;
  onNotes: () => void;
  onExport: () => void;
  onFavorite: () => void;
  /** "Đánh dấu đã nghe xong" (reading) or "Nghe lại từ đầu" (completed). */
  onStatus: (status: 'completed' | 'unread') => void;
  /** Own book: delete it. Public book: take it off the shelf. */
  onRemove: () => void;
}

/** A book on the shelf: cover, category, favourite heart, progress and the actions that fit its state. */
export const BookCard: React.FC<BookCardProps> = ({ book, onRead, onEdit, onNotes, onExport, onFavorite, onStatus, onRemove }) => {
  const fraction = progressFraction(book);
  const status = book.progress?.status ?? 'unread';
  const favorite = !!book.progress?.is_favorite;
  const mine = book.is_mine !== false;
  const author = book.author && book.author !== 'Unknown' ? book.author : '';
  return (
    <article className="book-card">
      <div className="cover-wrap">
        <BookCover title={book.title} url={book.cover_url} />
        <button className={`fav-btn ${favorite ? 'on' : ''}`} onClick={onFavorite} aria-pressed={favorite} aria-label={favorite ? `Bỏ yêu thích ${book.title}` : `Yêu thích ${book.title}`} title="Yêu thích">
          <Heart size={17} fill={favorite ? 'currentColor' : 'none'} />
        </button>
        {book.is_public && <span className="source-chip">Hệ thống</span>}
        {status === 'completed' && <span className="done-chip"><CheckCheck size={13} /> Đã xong</span>}
      </div>
      <div className="book-card-body">
        {book.category && <span className="category-chip">{book.category.name}</span>}
        <h3 className="book-card-title" title={book.title}>{book.title}</h3>
        <p className="book-card-author">{author || `${formatNumber(book.total_words)} từ`}</p>
        <div className="progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(fraction * 100)} aria-label={`Tiến độ ${book.title}`}>
          <div className="progress-fill" style={{ width: `${fraction * 100}%` }} />
        </div>
        <p className="book-card-meta">
          {Math.round(fraction * 100)}%{book.progress?.last_read_at && fraction > 0 ? ` · ${formatDateTime(book.progress.last_read_at)}` : ''}
        </p>
        <div className="card-actions">
          <button className="btn-primary" onClick={onRead}>{playLabel(status)}</button>
          <button className="btn-ghost icon" onClick={onEdit} aria-label={`Sửa thông tin ${book.title}`} title="Sửa thông tin" hidden={!mine}><Pencil size={16} /></button>
          <button className="btn-ghost icon" onClick={onNotes} aria-label={`Trích dẫn của ${book.title}`} title="Trích dẫn yêu thích"><NotebookText size={16} /></button>
          <button className="btn-ghost icon" onClick={onExport} aria-label={`Xuất audio ${book.title}`} title="Xuất audio"><Download size={16} /></button>
          {status === 'reading' && <button className="btn-ghost icon" onClick={() => onStatus('completed')} aria-label={`Đánh dấu đã nghe xong ${book.title}`} title="Đánh dấu đã nghe xong"><CheckCheck size={16} /></button>}
          {status === 'completed' && <button className="btn-ghost icon" onClick={() => onStatus('unread')} aria-label={`Nghe lại ${book.title} từ đầu`} title="Nghe lại từ đầu"><RotateCcw size={16} /></button>}
          <button className="btn-ghost icon danger" onClick={onRemove} aria-label={mine ? `Xóa ${book.title}` : `Gỡ ${book.title} khỏi kệ`} title={mine ? 'Xóa' : 'Gỡ khỏi kệ'}>
            {mine ? <Trash2 size={16} /> : <Unplug size={16} />}
          </button>
        </div>
      </div>
    </article>
  );
};
