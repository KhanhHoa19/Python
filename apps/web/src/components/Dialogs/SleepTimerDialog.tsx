import React, { useState } from 'react';
import { CUSTOM_MINUTES_MAX, MINUTE_PRESETS, SleepSetting, parseCustomMinutes } from '../../lib/sleepTimer.ts';
import { Modal } from '../common/Modal.tsx';

interface SleepTimerDialogProps {
  current: SleepSetting | null;
  onSelect: (setting: SleepSetting | null) => void;
  onClose: () => void;
}

/** Hẹn giờ tắt: pick a countdown or "stop at the end of this chapter". The last 10 s fade out. */
export const SleepTimerDialog: React.FC<SleepTimerDialogProps> = ({ current, onSelect, onClose }) => {
  const [custom, setCustom] = useState('');
  const customMinutes = parseCustomMinutes(custom);

  const choose = (setting: SleepSetting | null) => {
    onSelect(setting);
    onClose();
  };

  return (
    <Modal title="Hẹn giờ tắt" onClose={onClose} width={420}>
      <div className="modal-form">
        <p className="dialog-text">Âm lượng giảm dần trong 10 giây cuối rồi tự tạm dừng và lưu vị trí đọc.</p>
        <div className="choice-grid" role="group" aria-label="Thời gian hẹn">
          {MINUTE_PRESETS.map((minutes) => (
            <button key={minutes} className={`choice ${current?.kind === 'minutes' && current.minutes === minutes ? 'selected' : ''}`} onClick={() => choose({ kind: 'minutes', minutes })}>
              {minutes} phút
            </button>
          ))}
        </div>
        <form className="custom-row" onSubmit={(e) => { e.preventDefault(); if (customMinutes) choose({ kind: 'minutes', minutes: customMinutes }); }}>
          <label htmlFor="sleep-custom">Tùy chỉnh</label>
          <input id="sleep-custom" className="number-input" inputMode="numeric" placeholder={`1–${CUSTOM_MINUTES_MAX}`} value={custom} onChange={(e) => setCustom(e.target.value)} />
          <span className="muted">phút</span>
          <button className="btn-secondary small" type="submit" disabled={!customMinutes}>Đặt</button>
        </form>
        <button className={`choice wide ${current?.kind === 'chapter' ? 'selected' : ''}`} onClick={() => choose({ kind: 'chapter' })}>
          Dừng khi hết chương này
        </button>
        <div className="modal-actions spread">
          <button className="btn-ghost danger" onClick={() => choose(null)} disabled={!current}>Tắt hẹn giờ</button>
          <button className="btn-secondary" onClick={onClose}>Đóng</button>
        </div>
      </div>
    </Modal>
  );
};
