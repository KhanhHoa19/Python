import React, { useState } from 'react';
import { cloneVoice } from '../../api/voicesApi.ts';
import { Voice } from '../../types/voice.ts';
import { Modal } from '../common/Modal.tsx';

/** S04 – "Thêm giọng mới": clone a voice from a short sample (needs the owner's consent). */
interface CloneVoiceDialogProps {
  sampleSeconds: [number, number];
  onClose: () => void;
  onCreated: (voice: Voice) => void;
}

export const CloneVoiceDialog: React.FC<CloneVoiceDialogProps> = ({ sampleSeconds, onClose, onCreated }) => {
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
          <label htmlFor="clone-sample">File mẫu ({sampleSeconds[0]}–{sampleSeconds[1]} giây, WAV/MP3)</label>
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
