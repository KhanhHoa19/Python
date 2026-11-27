import React, { useState } from 'react';
import { updateSettings } from '../../api/settingsApi.ts';
import { useApp } from '../../context/AppContext.tsx';
import { AmbientTrack } from '../../types/ambient.ts';
import { AppSettings } from '../../types/settings.ts';
import { Modal } from '../common/Modal.tsx';

interface AmbientDialogProps {
  tracks: AmbientTrack[];
  onClose: () => void;
}

/** Âm thanh nền: pick a sound from the library, its volume, and whether a chime marks each new chapter. */
export const AmbientDialog: React.FC<AmbientDialogProps> = ({ tracks, onClose }) => {
  const { settings, applySettings, showError } = useApp();
  const [error, setError] = useState<string | null>(null);
  if (!settings) return null;
  const track = settings.ambient_track ?? 0;
  const volume = settings.ambient_volume ?? 0.4;
  const chime = settings.chapter_chime ?? true;

  const save = async (changes: Partial<AppSettings>) => {
    try {
      applySettings(await updateSettings({ ...settings, ...changes }));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không lưu được.');
      showError('Không lưu được cài đặt âm thanh nền.');
    }
  };

  return (
    <Modal title="Âm thanh nền" onClose={onClose} width={460}>
      <div className="modal-form">
        <ul className="voice-list" role="radiogroup" aria-label="Âm thanh nền">
          <li className="voice-row">
            <label><input type="radio" name="ambient" checked={track === 0} onChange={() => void save({ ambient_track: 0 })} /> Tắt</label>
          </li>
          {tracks.map((t) => (
            <li key={t.id} className="voice-row">
              <label><input type="radio" name="ambient" checked={track === t.id} onChange={() => void save({ ambient_track: t.id })} /> {t.name}</label>
            </li>
          ))}
        </ul>
        {tracks.length === 0 && <p className="muted">Quản trị viên chưa thêm âm thanh nền nào.</p>}

        <div className="form-group">
          <label htmlFor="ambient-volume">Âm lượng nền: {Math.round(volume * 100)}%</label>
          <input
            id="ambient-volume"
            type="range"
            min={0}
            max={100}
            step={5}
            value={Math.round(volume * 100)}
            disabled={track === 0}
            onChange={(e) => applySettings({ ...settings, ambient_volume: Number(e.target.value) / 100 })}
            onPointerUp={() => void save({ ambient_volume: volume })}
            onKeyUp={() => void save({ ambient_volume: volume })}
          />
        </div>

        <label className="checkbox-row">
          <input type="checkbox" checked={chime} onChange={(e) => void save({ chapter_chime: e.target.checked })} />
          Phát tiếng chuông khi sang chương mới
        </label>
        {error && <p className="status-text error" role="alert">{error}</p>}
        <div className="modal-actions"><button className="btn-primary" onClick={onClose}>Xong</button></div>
      </div>
    </Modal>
  );
};
