import React from 'react';
import { Pencil, Play, Trash2 } from 'lucide-react';
import { formatDateTime } from '../../lib/format.ts';
import { Note } from '../../types/note.ts';

interface NoteCardProps {
  note: Note;
  onPlay: () => void;
  onGo: () => void;
  onEdit: () => void;
  onDelete: () => void;
}

export const NoteCard: React.FC<NoteCardProps> = ({ note, onPlay, onGo, onEdit, onDelete }) => (
  <article className="note-card">
    <p className="muted">📄 {note.book_title} · câu {note.sentence_index + 1} · {formatDateTime(note.created_at)}</p>
    <blockquote className="excerpt">“{note.excerpt}”</blockquote>
    {note.note_text && <p className="note-text">📝 {note.note_text}</p>}
    <div className="card-actions">
      <button className="btn-primary small" onClick={onPlay}><Play size={14} /> Nghe lại</button>
      <button className="btn-secondary small" onClick={onGo}>Đến câu này</button>
      <button className="btn-secondary small" onClick={onEdit}><Pencil size={14} /> Sửa</button>
      <button className="btn-danger small" onClick={onDelete}><Trash2 size={14} /> Xóa</button>
    </div>
  </article>
);
