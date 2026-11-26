import React, { useEffect, useState } from 'react';
import { checkNetwork, verifyTts } from '../../api/healthApi.ts';
import { updateSettings } from '../../api/settingsApi.ts';
import { useApp } from '../../context/AppContext.tsx';
import { formatNumber, usageRatio } from '../../lib/format.ts';
import { VoiceOptions } from '../common/VoiceOptions.tsx';
import { SPEED_LEVELS } from '../../types/player.ts';
import { Modal } from '../common/Modal.tsx';

interface SettingsDialogProps {
  onClose: () => void;
}

type CheckState = { state: 'idle' | 'running' | 'ok' | 'fail'; detail: string };
const CHECKS = [
  ['dns', 'DNS'],
  ['port', 'Cổng 443'],
  ['latency', 'Độ trễ mạng'],
  ['synth', 'Thử đọc 1 câu'],
] as const;
const IDLE: Record<string, CheckState> = Object.fromEntries(CHECKS.map(([key]) => [key, { state: 'idle', detail: '' }]));
const ICONS = { idle: '·', running: '⏳', ok: '✔', fail: '✖' };

/** S05 – Kết nối & Cài đặt. API key stays in the backend's .env and is never shown here. */
export const SettingsDialog: React.FC<SettingsDialogProps> = ({ onClose }) => {
  const { settings, voices, applySettings, refreshSettings, toast } = useApp();
  const [prefetch, setPrefetch] = useState(String(settings?.prefetch_count ?? 2));
  const [speed, setSpeed] = useState(String(settings?.default_speed ?? 1));
  const [voice, setVoice] = useState(settings?.default_voice ?? '');
  const [limit, setLimit] = useState(String(settings?.daily_char_limit ?? 0));
  const [checks, setChecks] = useState<Record<string, CheckState>>(IDLE);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refreshSettings(); // fresh "đã dùng hôm nay"
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const set = (key: string, value: CheckState) => setChecks((prev) => ({ ...prev, [key]: value }));

  const runChecks = async () => {
    setChecking(true);
    CHECKS.forEach(([key]) => set(key, { state: 'running', detail: '' }));
    try {
      const network = await checkNetwork();
      const byName = new Map(network.checks.map((c) => [c.name, c]));
      for (const key of ['dns', 'port', 'latency']) {
        const check = byName.get(key);
        if (network.skipped) set(key, { state: 'ok', detail: 'bỏ qua (nhà cung cấp chạy offline)' });
        else if (check) set(key, { state: check.ok ? 'ok' : 'fail', detail: check.detail });
        else set(key, { state: 'fail', detail: 'không chạy được vì bước trước lỗi' });
      }
      const verify = await verifyTts();
      set('synth', verify.ok ? { state: 'ok', detail: 'thành công' } : { state: 'fail', detail: verify.error ?? 'thất bại' });
    } catch (err) {
      const detail = err instanceof Error ? err.message : 'Lỗi không xác định';
      CHECKS.forEach(([key]) => set(key, { state: 'fail', detail }));
    }
    setChecking(false);
  };

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    const limitValue = Number(limit.replace(/\./g, '') || 0);
    if (!Number.isInteger(limitValue) || limitValue < 0) return setError('Giới hạn ký tự phải là số nguyên không âm.');
    setError(null);
    try {
      applySettings(
        await updateSettings({
          prefetch_count: Number(prefetch),
          default_speed: Number(speed),
          default_voice: voice,
          daily_char_limit: limitValue,
        }),
      );
      toast('Đã lưu cài đặt.');
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không lưu được cài đặt.');
    }
  };

  const used = settings?.chars_used_today ?? 0;
  const limitNow = settings?.daily_char_limit ?? 0;
  const ratio = usageRatio(used, limitNow);

  return (
    <Modal title="Kết nối & Cài đặt" onClose={onClose} width={580}>
      <form className="modal-form" onSubmit={save}>
        <h4 className="section-title">Kết nối</h4>
        <p>Nhà cung cấp: <strong>{settings?.provider ?? '…'}</strong></p>
        <p className="muted">API Key đặt trong file .env phía backend, không nhập ở đây.</p>
        <div><button type="button" className="btn-secondary" onClick={runChecks} disabled={checking}>Kiểm tra kết nối</button></div>
        <ul className="check-list" aria-live="polite">
          {CHECKS.map(([key, label]) => (
            <li key={key} className={`check ${checks[key].state}`}>
              <span aria-hidden="true">{ICONS[checks[key].state]}</span> {label} {checks[key].detail && <span className="muted">{checks[key].detail}</span>}
            </li>
          ))}
        </ul>

        <h4 className="section-title">Cài đặt đọc</h4>
        <div className="form-grid">
          <label htmlFor="set-prefetch">Số câu tải trước</label>
          <select id="set-prefetch" value={prefetch} onChange={(e) => setPrefetch(e.target.value)}>
            {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
          <label htmlFor="set-speed">Tốc độ mặc định</label>
          <select id="set-speed" value={speed} onChange={(e) => setSpeed(e.target.value)}>
            {SPEED_LEVELS.map((s) => <option key={s} value={s}>{s}x</option>)}
          </select>
          <label htmlFor="set-voice">Giọng mặc định</label>
          <select id="set-voice" value={voice} onChange={(e) => setVoice(e.target.value)}>
            <VoiceOptions voices={voices} extraValue={voice} />
          </select>
          <label htmlFor="set-limit">Giới hạn ký tự/ngày</label>
          <span>
            <input id="set-limit" className="number-input wide" inputMode="numeric" value={limit} onChange={(e) => setLimit(e.target.value)} />{' '}
            <span className="muted">(0 = không giới hạn)</span>
          </span>
        </div>
        <p className="muted">Đã dùng hôm nay: {formatNumber(used)} ký tự{limitNow > 0 && ` / ${formatNumber(limitNow)}`}</p>
        <progress className={`progress-native ${ratio >= 0.8 ? 'warn' : ''}`} value={ratio} max={1} aria-label="Mức dùng ký tự hôm nay" />

        {error && <p className="status-text error" role="alert">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={onClose}>Đóng</button>
          <button type="submit" className="btn-primary">Lưu cài đặt</button>
        </div>
      </form>
    </Modal>
  );
};
