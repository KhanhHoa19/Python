import React, { useRef, useState } from 'react';
import { Pause, Pencil, Play, Plus, Trash2 } from 'lucide-react';
import { addAmbient, deleteAmbient, listAmbient, renameAmbient } from '../../api/ambientApi.ts';
import { useApp } from '../../context/AppContext.tsx';
import { useAsyncData } from '../../hooks/useAsyncData.ts';
import { formatBytes } from '../../lib/admin.ts';
import { AmbientTrack } from '../../types/ambient.ts';
import { ConfirmDialog } from '../common/ConfirmDialog.tsx';
import { Modal } from '../common/Modal.tsx';
import { EmptyState, ErrorState, LoadingState } from '../common/StateViews.tsx';

const ACCEPT = '.mp3,.ogg,.wav,.m4a';
const MAX_BYTES = 15 * 1024 * 1024;

/** Quản trị › Âm thanh nền: the library every reader chooses their background sound from. */
export const AmbientPanel: React.FC<{ active: boolean }> = ({ active }) => {
  const { toast, showError } = useApp();
  const tracks = useAsyncData(listAmbient, [], active);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<AmbientTrack | null>(null);
  const [toDelete, setToDelete] = useState<AmbientTrack | null>(null);
  const [playing, setPlaying] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const stop = () => {
    audioRef.current?.pause();
    audioRef.current = null;
    setPlaying(null);
  };

  const preview = (track: AmbientTrack) => {
    if (playing === track.id) return stop();
    stop();
    const audio = new Audio(track.url);
    audio.onended = () => setPlaying(null);
    audioRef.current = audio;
    setPlaying(track.id);
    audio.play().catch(() => stop());
  };

  const remove = async () => {
    const target = toDelete;
    setToDelete(null);
    if (!target) return;
    if (playing === target.id) stop();
    try {
      await deleteAmbient(target.id);
      toast(`Đã xóa "${target.name}"`);
      tracks.reload();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Không xóa được.');
    }
  };

  if (!tracks.data && !tracks.error) return <LoadingState />;
  if (tracks.error) return <ErrorState message={tracks.error} onRetry={tracks.reload} />;

  return (
    <>
      <div className="panel-bar">
        <p className="muted">Mọi người chọn âm thanh nền của mình từ danh sách này (nút “Nhạc nền” ở Phòng Đọc). Chỉ thêm nhạc không dính bản quyền. MP3, OGG, WAV hoặc M4A, tối đa 15 MB.</p>
        <button className="btn-primary" onClick={() => setAdding(true)}><Plus size={16} /> Thêm âm thanh</button>
      </div>
      {(tracks.data ?? []).length === 0 ? (
        <EmptyState title="Chưa có âm thanh nền nào." hint="Thêm một bản nhạc hoặc tiếng mưa, lò sưởi… để người nghe chọn." />
      ) : (
        <ul className="studio-list">
          {(tracks.data ?? []).map((t) => (
            <li key={t.id} className="studio-row">
              <div className="studio-info">
                <span className="studio-name">{t.name}</span>
                <span className="muted">{formatBytes(t.size_bytes)}</span>
              </div>
              <span className="row-actions">
                <button className="btn-secondary small" onClick={() => preview(t)}>{playing === t.id ? <><Pause size={14} /> Dừng</> : <><Play size={14} /> Nghe thử</>}</button>
                <button className="btn-ghost small" aria-label={`Đổi tên ${t.name}`} onClick={() => setEditing(t)}><Pencil size={14} /></button>
                <button className="btn-danger small" aria-label={`Xóa ${t.name}`} onClick={() => setToDelete(t)}><Trash2 size={14} /></button>
              </span>
            </li>
          ))}
        </ul>
      )}
      {adding && <AddDialog onClose={() => setAdding(false)} onAdded={(t) => { setAdding(false); toast(`Đã thêm "${t.name}"`); tracks.reload(); }} />}
      {editing && <RenameDialog track={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); tracks.reload(); }} />}
      {toDelete && (
        <ConfirmDialog
          title="Xóa âm thanh nền"
          message={`Xóa "${toDelete.name}"? Ai đang dùng bản này sẽ không còn nghe nhạc nền cho tới khi chọn bản khác.`}
          confirmLabel="Xóa"
          danger
          onConfirm={() => void remove()}
          onCancel={() => setToDelete(null)}
        />
      )}
    </>
  );
};

const AddDialog: React.FC<{ onClose: () => void; onAdded: (t: AmbientTrack) => void }> = ({ onClose, onAdded }) => {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const choose = (picked: File | undefined) => {
    if (!picked) return;
    const extension = picked.name.slice(picked.name.lastIndexOf('.')).toLowerCase();
    if (!ACCEPT.split(',').includes(extension)) return setError('Chỉ nhận MP3, OGG, WAV hoặc M4A.');
    if (picked.size > MAX_BYTES) return setError('File vượt quá 15 MB.');
    setError(null);
    setFile(picked);
    if (!name.trim()) setName(picked.name.replace(/\.[^.]+$/, '').replace(/[_]+/g, ' ').slice(0, 100));
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file || !name.trim()) return;
    setBusy(true);
    try {
      onAdded(await addAmbient(name.trim(), file));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thêm được.');
      setBusy(false);
    }
  };

  return (
    <Modal title="Thêm âm thanh nền" onClose={busy ? () => undefined : onClose} width={460}>
      <form className="modal-form" onSubmit={submit}>
        <div className="form-group">
          <label htmlFor="ambient-file">File âm thanh (MP3, OGG, WAV, M4A · tối đa 15 MB)</label>
          <input id="ambient-file" type="file" accept={ACCEPT} onChange={(e) => choose(e.target.files?.[0])} />
        </div>
        <div className="form-group">
          <label htmlFor="ambient-name">Tên hiển thị</label>
          <input id="ambient-name" value={name} maxLength={100} onChange={(e) => setName(e.target.value)} />
        </div>
        {error && <p className="status-text error" role="alert">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={onClose} disabled={busy}>Hủy</button>
          <button type="submit" className="btn-primary" disabled={busy || !file || !name.trim()}>{busy ? 'Đang tải lên…' : 'Thêm'}</button>
        </div>
      </form>
    </Modal>
  );
};

const RenameDialog: React.FC<{ track: AmbientTrack; onClose: () => void; onSaved: () => void }> = ({ track, onClose, onSaved }) => {
  const [name, setName] = useState(track.name);
  const [error, setError] = useState<string | null>(null);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await renameAmbient(track.id, name);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không đổi được tên.');
    }
  };
  return (
    <Modal title="Đổi tên âm thanh" onClose={onClose} width={440}>
      <form className="modal-form" onSubmit={submit}>
        <div className="form-group">
          <label htmlFor="ambient-rename">Tên</label>
          <input id="ambient-rename" value={name} maxLength={100} onChange={(e) => setName(e.target.value)} autoFocus />
        </div>
        {error && <p className="status-text error" role="alert">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={onClose}>Hủy</button>
          <button type="submit" className="btn-primary" disabled={!name.trim()}>Lưu</button>
        </div>
      </form>
    </Modal>
  );
};
