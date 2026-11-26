import React, { useState } from 'react';
import { Play, Trash2 } from 'lucide-react';
import { cloneVoice, deleteVoice, fetchVoicePreview } from '../../api/voicesApi.ts';
import { useApp } from '../../context/AppContext.tsx';
import { useBlobAudio } from '../../hooks/useBlobAudio.ts';
import { describeVoice } from '../../lib/voices.ts';
import { Voice } from '../../types/voice.ts';
import { ConfirmDialog } from '../common/ConfirmDialog.tsx';
import { Modal } from '../common/Modal.tsx';

interface VoicesDialogProps {
  onClose: () => void;
}

/** S04 – Chọn giọng & Thêm giọng mới. */
export const VoicesDialog: React.FC<VoicesDialogProps> = ({ onClose }) => {
  const { voiceList, voiceId, setVoiceId, refreshVoices, toast } = useApp();
  const [tab, setTab] = useState<'builtin' | 'custom'>('builtin');
  const [choice, setChoice] = useState<string | null>(voiceId);
  const [cloning, setCloning] = useState(false);
  const [toDelete, setToDelete] = useState<Voice | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const { playBlob } = useBlobAudio();

  const voices = (voiceList?.voices ?? []).filter((v) => v.is_custom === (tab === 'custom'));

  const preview = async (voice: Voice) => {
    setMessage('Đang tải giọng nghe thử…');
    try {
      await playBlob(await fetchVoicePreview(voice.voice_id));
      setMessage(null);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Không nghe thử được.');
    }
  };

  const confirmDelete = async () => {
    if (!toDelete) return;
    try {
      await deleteVoice(toDelete.voice_id);
      await refreshVoices();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Không xóa được giọng.');
    }
    setToDelete(null);
  };

  if (cloning) {
    return (
      <CloneVoiceDialog
        onClose={() => setCloning(false)}
        onCreated={async (voice) => {
          await refreshVoices();
          setChoice(voice.voice_id);
          setTab('custom');
          setCloning(false);
          toast(`Đã tạo giọng "${voice.display_name}"`);
        }}
      />
    );
  }

  return (
    <Modal title="Giọng đọc" onClose={onClose} width={640}>
      <div className="modal-form">
        {voiceList?.warning && <p className="status-text warn">{voiceList.warning}</p>}
        <div className="segmented" role="tablist">
          {(['builtin', 'custom'] as const).map((id) => (
            <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>
              {id === 'builtin' ? 'Có sẵn' : 'Giọng của tôi'}
            </button>
          ))}
        </div>

        <ul className="voice-list">
          {voices.length === 0 && <li className="muted">{tab === 'custom' ? 'Bạn chưa có giọng riêng nào.' : 'Chưa có giọng nào.'}</li>}
          {voices.map((voice) => (
            <li key={voice.voice_id} className="voice-row">
              <label>
                <input type="radio" name="voice" checked={choice === voice.voice_id} onChange={() => setChoice(voice.voice_id)} />
                {describeVoice(voice)}
              </label>
              <span className="row-actions">
                <button className="btn-secondary small" onClick={() => preview(voice)}><Play size={14} /> Nghe thử</button>
                {voice.is_custom && (
                  <button className="btn-danger small" aria-label={`Xóa giọng ${voice.display_name}`} onClick={() => setToDelete(voice)}>
                    <Trash2 size={14} />
                  </button>
                )}
              </span>
            </li>
          ))}
        </ul>
        {message && <p className="status-text" role="status">{message}</p>}
        {voiceList && !voiceList.supports_cloning && (
          <p className="status-text warn">Nhà cung cấp hiện tại không hỗ trợ tạo giọng.</p>
        )}

        <div className="modal-actions spread">
          <button className="btn-secondary" disabled={!voiceList?.supports_cloning} onClick={() => setCloning(true)}>+ Thêm giọng mới</button>
          <span>
            <button className="btn-secondary" onClick={onClose}>Hủy</button>{' '}
            <button className="btn-primary" disabled={!choice} onClick={() => (choice && setVoiceId(choice), onClose())}>Dùng giọng này</button>
          </span>
        </div>
      </div>
      {toDelete && (
        <ConfirmDialog
          title="Xóa giọng"
          message={`Xóa giọng "${toDelete.display_name}"?`}
          confirmLabel="Xóa"
          danger
          onConfirm={confirmDelete}
          onCancel={() => setToDelete(null)}
        />
      )}
    </Modal>
  );
};

interface CloneVoiceDialogProps {
  onClose: () => void;
  onCreated: (voice: Voice) => void;
}

const CloneVoiceDialog: React.FC<CloneVoiceDialogProps> = ({ onClose, onCreated }) => {
  const [name, setName] = useState('');
  const [sample, setSample] = useState<File | null>(null);
  const [language, setLanguage] = useState('vi');
  const [gender, setGender] = useState<'female' | 'male'>('female');
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!sample || !consent || !name.trim()) return setError('Hãy nhập tên, chọn file mẫu và tick đồng thuận.');
    setBusy(true);
    setError(null);
    try {
      onCreated(await cloneVoice({ sample, name: name.trim(), language, gender, consent }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tạo được giọng.');
      setBusy(false);
    }
  };

  return (
    <Modal title="Thêm giọng mới" onClose={busy ? () => undefined : onClose}>
      <form className="modal-form" onSubmit={submit}>
        <div className="form-group">
          <label htmlFor="clone-name">Tên giọng</label>
          <input id="clone-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </div>
        <div className="form-group">
          <label htmlFor="clone-sample">File mẫu (5–15 giây, WAV/MP3)</label>
          <input id="clone-sample" type="file" accept="audio/*,.wav,.mp3,.m4a,.ogg" onChange={(e) => setSample(e.target.files?.[0] ?? null)} />
        </div>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="clone-language">Ngôn ngữ</label>
            <select id="clone-language" value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="vi">Tiếng Việt</option>
              <option value="en">English</option>
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="clone-gender">Giới tính</label>
            <select id="clone-gender" value={gender} onChange={(e) => setGender(e.target.value as 'female' | 'male')}>
              <option value="female">Nữ</option>
              <option value="male">Nam</option>
            </select>
          </div>
        </div>
        <label className="checkbox-row">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          Tôi xác nhận đây là giọng của tôi hoặc tôi được chủ giọng đồng ý.
        </label>
        {busy && <p className="status-text" role="status"><span className="spinner small" /> Đang tạo giọng… (có thể mất vài chục giây)</p>}
        {error && <p className="status-text error" role="alert">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={onClose} disabled={busy}>Hủy</button>
          <button type="submit" className="btn-primary" disabled={busy || !sample || !consent}>Tạo giọng</button>
        </div>
      </form>
    </Modal>
  );
};
