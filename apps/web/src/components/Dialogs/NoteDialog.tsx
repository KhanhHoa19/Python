import React, { useState } from 'react';
import { createNote, updateNote } from '../../api/notesApi.ts';
import { SentenceSelection } from '../../hooks/useTextSelection.ts';
import { Note } from '../../types/note.ts';
import { Modal } from '../common/Modal.tsx';

type NoteDialogProps =
  | { mode: 'create'; bookId: number; selection: SentenceSelection; onSaved: (note: Note) => void; onClose: () => void }
  | { mode: 'edit'; note: Note; onSaved: (note: Note) => void; onClose: () => void };

/** S06 – tạo ghi chú mới (từ Phòng Đọc) hoặc sửa ghi chú. */
export const NoteDialog: React.FC<NoteDialogProps> = (props) => {
  const excerpt = props.mode === 'create' ? props.selection.excerpt : props.note.excerpt;
  const [text, setText] = useState(props.mode === 'edit' ? props.note.note_text : '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const saved =
        props.mode === 'create'
          ? await createNote({
              book_id: props.bookId,
              sentence_index: props.selection.sentenceIndex,
              start_offset: props.selection.startOffset,
              end_offset: props.selection.endOffset,
              note_text: text.trim(),
            })
          : await updateNote(props.note.id, text.trim());
      props.onSaved(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không lưu được ghi chú.');
      setBusy(false);
    }
  };

  return (
    <Modal title={props.mode === 'create' ? 'Ghi chú mới' : 'Sửa ghi chú'} onClose={props.onClose}>
      <form className="modal-form" onSubmit={submit}>
        <div className="form-group">
          <span className="field-label">Đoạn đã chọn</span>
          <blockquote className="excerpt">“{excerpt.length > 200 ? `${excerpt.slice(0, 197)}…` : excerpt}”</blockquote>
        </div>
        <div className="form-group">
          <label htmlFor="note-text">Ghi chú của bạn</label>
          <textarea id="note-text" rows={4} value={text} onChange={(e) => setText(e.target.value)} autoFocus />
        </div>
        {error && <p className="status-text error" role="alert">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={props.onClose}>Hủy</button>
          <button type="submit" className="btn-primary" disabled={busy}>Lưu ghi chú</button>
        </div>
      </form>
    </Modal>
  );
};
