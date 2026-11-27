import React from 'react';
import { Pause, Pencil, Play, Trash2 } from 'lucide-react';
import { formatDateTime } from '../../lib/format.ts';
import { emotionLabel } from '../../lib/quotes.ts';
import { Note } from '../../types/note.ts';

interface QuoteCardProps {
  note: Note;
  /** This quote is the one the playlist is playing now. */
  playing: boolean;
  onPlay: () => void;
  onGo: () => void;
  onEdit: () => void;
  onDelete: () => void;
}

/** A favourite quote: the passage in large serif type with its neighbouring sentences, the feeling and the actions. */
export const QuoteCard: React.FC<QuoteCardProps> = ({ note, playing, onPlay, onGo, onEdit, onDelete }) => (
  <article className={`quote-card ${playing ? 'playing' : ''}`} aria-current={playing ? 'true' : undefined}>
    <div className="quote-head">
      {note.emotion_tag && <span className={`chip static tag-${note.emotion_tag} selected`}>{emotionLabel(note.emotion_tag)}</span>}
      <span className="muted quote-source">{note.book_title} · câu {note.sentence_index + 1} · {formatDateTime(note.created_at)}</span>
    </div>
    {note.context_before && <p className="quote-context">…{note.context_before}</p>}
    <blockquote className="quote-text">“{note.excerpt}”</blockquote>
    {note.context_after && <p className="quote-context">{note.context_after}…</p>}
    {note.note_text && <p className="note-text">📝 {note.note_text}</p>}
    <div className="card-actions">
      <button className="btn-primary small" onClick={onPlay}>{playing ? <Pause size={14} /> : <Play size={14} />} {playing ? 'Đang phát' : 'Nghe lại'}</button>
      <button className="btn-secondary small" onClick={onGo}>Đến câu này</button>
      <button className="btn-ghost small" onClick={onEdit}><Pencil size={14} /> Sửa</button>
      <button className="btn-ghost small danger" onClick={onDelete}><Trash2 size={14} /> Xóa</button>
    </div>
  </article>
);
