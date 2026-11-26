import React, { useRef, useState } from 'react';
import { Upload } from 'lucide-react';
import { uploadBookFile } from '../../api/booksApi.ts';
import { BookUploadResponse } from '../../types/book.ts';
import { Modal } from '../common/Modal.tsx';

const ACCEPT = '.pdf,.docx,.txt,.md';
const MAX_BYTES = 10 * 1024 * 1024;

interface UploadDialogProps {
  onClose: () => void;
  onUploaded: (result: BookUploadResponse) => void;
}

/** S02 – Thêm tài liệu. */
export const UploadDialog: React.FC<UploadDialogProps> = ({ onClose, onUploaded }) => {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [author, setAuthor] = useState('');
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const choose = (picked: File | undefined) => {
    if (!picked) return;
    const extension = picked.name.slice(picked.name.lastIndexOf('.')).toLowerCase();
    if (!ACCEPT.split(',').includes(extension)) return setError('Định dạng không được hỗ trợ.');
    if (picked.size > MAX_BYTES) return setError('File vượt quá 10 MB.');
    setError(null);
    setFile(picked);
    if (!title.trim()) setTitle(picked.name.replace(/\.[^.]+$/, '').replace(/_/g, ' '));
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      onUploaded(await uploadBookFile(file, title.trim(), author.trim()));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Tải lên thất bại.';
      setError(/scanned|OCR/i.test(message) ? 'Không đọc được chữ. Có thể đây là PDF scan (chưa hỗ trợ OCR).' : message);
      setBusy(false);
    }
  };

  return (
    <Modal title="Thêm tài liệu" onClose={busy ? () => undefined : onClose}>
      <form className="modal-form" onSubmit={submit}>
        <div
          className={`dropzone ${dragging ? 'drag-over' : ''}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => (e.preventDefault(), setDragging(true))}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => (e.preventDefault(), setDragging(false), choose(e.dataTransfer.files[0]))}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), inputRef.current?.click())}
        >
          <Upload className="dropzone-icon" size={32} />
          <p className="prompt-primary">{file ? file.name : 'Kéo thả file vào đây hoặc bấm để chọn'}</p>
          <p className="prompt-secondary">Hỗ trợ: PDF (có lớp chữ), DOCX, TXT, MD · Tối đa 10 MB</p>
          <input ref={inputRef} type="file" accept={ACCEPT} hidden onChange={(e) => choose(e.target.files?.[0])} />
        </div>

        <div className="form-group">
          <label htmlFor="upload-title">Tên tài liệu</label>
          <input id="upload-title" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div className="form-group">
          <label htmlFor="upload-author">Tác giả (không bắt buộc)</label>
          <input id="upload-author" value={author} onChange={(e) => setAuthor(e.target.value)} />
        </div>

        {busy && <p className="status-text" role="status"><span className="spinner small" /> Đang tải lên và tách câu…</p>}
        {error && <p className="status-text error" role="alert">{error}</p>}

        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={onClose} disabled={busy}>Hủy</button>
          <button type="submit" className="btn-primary" disabled={!file || busy}>Tải lên</button>
        </div>
      </form>
    </Modal>
  );
};
