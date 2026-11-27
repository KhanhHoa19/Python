import React, { useMemo, useState } from 'react';
import { Check, Pencil, Play, Plus, Star, Trash2 } from 'lucide-react';
import { deleteVoice, fetchVoicePreview, renameVoice } from '../api/voicesApi.ts';
import { updateSettings } from '../api/settingsApi.ts';
import { CloneVoiceDialog } from '../components/Dialogs/CloneVoiceDialog.tsx';
import { ConfirmDialog } from '../components/common/ConfirmDialog.tsx';
import { Modal } from '../components/common/Modal.tsx';
import { PageHeader } from '../components/common/PageHeader.tsx';
import { EmptyState } from '../components/common/StateViews.tsx';
import { useApp } from '../context/AppContext.tsx';
import { useBlobAudio } from '../hooks/useBlobAudio.ts';
import { cloneQuota, splitVoices } from '../lib/voices.ts';
import { Voice } from '../types/voice.ts';

interface VoicesPageProps {
  active: boolean;
}

/** S04 – Kho Giọng Đọc: system voices and the user's own clones; preview, set as default, rename, delete, clone. */
export const VoicesPage: React.FC<VoicesPageProps> = () => {
  const { voiceList, voices, settings, applySettings, refreshVoices, setVoiceId, toast, user } = useApp();
  const [tab, setTab] = useState<'system' | 'mine'>('system');
  const [cloning, setCloning] = useState(false);
  const [toDelete, setToDelete] = useState<Voice | null>(null);
  const [toRename, setToRename] = useState<Voice | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const { playBlob } = useBlobAudio();

  const { system, mine } = useMemo(() => splitVoices(voices), [voices]);
  const quota = cloneQuota(voiceList);
  const shown = tab === 'system' ? system : mine;
  const defaultVoice = settings?.default_voice ?? null;
  const canClone = !!voiceList?.supports_cloning && !quota.full;

  const preview = async (voice: Voice) => {
    setMessage('Đang tải giọng nghe thử…');
    try {
      await playBlob(await fetchVoicePreview(voice.voice_id));
      setMessage(null);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Không nghe thử được.');
    }
  };

  const makeDefault = async (voice: Voice) => {
    if (!settings) return;
    try {
      applySettings(await updateSettings({ ...settings, default_voice: voice.voice_id }));
      setVoiceId(voice.voice_id);
      toast(`Đã đặt "${voice.display_name}" làm giọng mặc định`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Không lưu được giọng mặc định.');
    }
  };

  const confirmDelete = async () => {
    if (!toDelete) return;
    try {
      await deleteVoice(toDelete.voice_id);
      await refreshVoices();
      toast(`Đã xóa giọng "${toDelete.display_name}"`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Không xóa được giọng.');
    }
    setToDelete(null);
  };

  return (
    <div className="voices-page">
      <PageHeader title="Kho Giọng Đọc" subtitle="Nghe thử, chọn giọng mặc định và tạo giọng riêng của bạn.">
        {voiceList && (
          <span className="muted" data-testid="voice-quota">
            {quota.max === null ? `${quota.used} giọng riêng` : `${quota.used}/${quota.max} giọng riêng`}
          </span>
        )}
        <button className="btn-primary" disabled={!canClone} onClick={() => setCloning(true)}><Plus size={16} /> Thêm giọng mới</button>
      </PageHeader>

      {voiceList?.warning && <p className="status-text warn">{voiceList.warning}</p>}
      {voiceList && !voiceList.supports_cloning && <p className="status-text warn">Nhà cung cấp hiện tại không hỗ trợ tạo giọng.</p>}
      {voiceList?.supports_cloning && quota.full && <p className="status-text warn">Bạn đã dùng hết {quota.max} giọng riêng. Hãy xóa một giọng để tạo giọng mới.</p>}

      <div className="segmented" role="tablist" aria-label="Nhóm giọng">
        <button role="tab" aria-selected={tab === 'system'} className={tab === 'system' ? 'active' : ''} onClick={() => setTab('system')}>Giọng hệ thống ({system.length})</button>
        <button role="tab" aria-selected={tab === 'mine'} className={tab === 'mine' ? 'active' : ''} onClick={() => setTab('mine')}>Giọng của tôi ({mine.length})</button>
      </div>

      {message && <p className="status-text" role="status">{message}</p>}

      {shown.length === 0 ? (
        <EmptyState title={tab === 'mine' ? 'Bạn chưa có giọng riêng nào.' : 'Chưa có giọng nào.'} hint={tab === 'mine' ? 'Tải lên một đoạn ghi âm ngắn để tạo giọng đọc của riêng bạn.' : undefined} />
      ) : (
        <ul className="studio-list">
          {shown.map((voice) => {
            const isDefault = voice.voice_id === defaultVoice;
            const canEdit = voice.is_mine || (user.role === 'admin' && voice.is_public);
            return (
              <li key={voice.voice_id} className={`studio-row ${isDefault ? 'is-default' : ''}`}>
                <div className="studio-info">
                  <span className="studio-name">{voice.display_name || voice.voice_id}</span>
                  <span className="muted">
                    {[voice.gender === 'female' ? 'Nữ' : voice.gender === 'male' ? 'Nam' : '', voice.language.toUpperCase(), voice.style ?? ''].filter(Boolean).join(' · ')}
                  </span>
                  <span className="chip-row">
                    {isDefault && <span className="chip static selected"><Check size={12} /> Mặc định</span>}
                    {voice.is_public && voice.is_custom && <span className="chip static">Giọng chung</span>}
                    {voice.is_custom && voice.is_mine && !voice.is_public && <span className="chip static">Riêng tư</span>}
                  </span>
                </div>
                <span className="row-actions">
                  <button className="btn-secondary small" onClick={() => preview(voice)}><Play size={14} /> Nghe thử</button>
                  <button className="btn-secondary small" disabled={isDefault} onClick={() => makeDefault(voice)}><Star size={14} /> Đặt mặc định</button>
                  {canEdit && voice.is_custom && (
                    <>
                      <button className="btn-ghost small" aria-label={`Đổi tên giọng ${voice.display_name}`} onClick={() => setToRename(voice)}><Pencil size={14} /></button>
                      <button className="btn-danger small" aria-label={`Xóa giọng ${voice.display_name}`} onClick={() => setToDelete(voice)}><Trash2 size={14} /></button>
                    </>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      )}

      {cloning && (
        <CloneVoiceDialog
          sampleSeconds={voiceList?.clone_sample_seconds ?? [5, 15]}
          onClose={() => setCloning(false)}
          onCreated={async (voice) => {
            await refreshVoices();
            setTab('mine');
            setCloning(false);
            toast(`Đã tạo giọng "${voice.display_name}"`);
          }}
        />
      )}
      {toRename && (
        <RenameVoiceDialog
          voice={toRename}
          onClose={() => setToRename(null)}
          onSaved={async () => {
            await refreshVoices();
            setToRename(null);
          }}
        />
      )}
      {toDelete && (
        <ConfirmDialog title="Xóa giọng" message={`Xóa giọng "${toDelete.display_name}"? Việc này không thể hoàn tác.`} confirmLabel="Xóa" danger onConfirm={confirmDelete} onCancel={() => setToDelete(null)} />
      )}
    </div>
  );
};

const RenameVoiceDialog: React.FC<{ voice: Voice; onClose: () => void; onSaved: () => void }> = ({ voice, onClose, onSaved }) => {
  const [name, setName] = useState(voice.display_name);
  const [error, setError] = useState<string | null>(null);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await renameVoice(voice.voice_id, name);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không đổi được tên.');
    }
  };
  return (
    <Modal title="Đổi tên giọng" onClose={onClose} width={440}>
      <form className="modal-form" onSubmit={submit}>
        <div className="form-group">
          <label htmlFor="voice-name">Tên giọng</label>
          <input id="voice-name" value={name} maxLength={100} onChange={(e) => setName(e.target.value)} autoFocus />
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
