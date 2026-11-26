import React, { useState } from 'react';
import { ChevronLeft, ChevronRight, Loader2, Pause, Play, SkipBack, SkipForward } from 'lucide-react';
import { formatNumber } from '../../lib/format.ts';
import { PlayerState, SPEED_LEVELS } from '../../types/player.ts';

interface PlayerControlsProps {
  state: PlayerState;
  index: number;
  total: number;
  speed: number;
  latencyMs: number;
  buffered: number;
  prefetch: number;
  onToggle: () => void;
  onSeek: (index: number) => void;
  onSpeed: (speed: number) => void;
}

const STATE_TEXT: Record<PlayerState, string> = {
  idle: '■ Đã dừng',
  loading: '⏳ Đang tải…',
  playing: '● Đang phát',
  paused: '❚❚ Tạm dừng',
  finished: '✔ Đã đọc xong',
};

/** Progress, transport buttons, speed, jump-to-sentence and status line of the reader. */
export const PlayerControls: React.FC<PlayerControlsProps> = (props) => {
  const { state, index, total, speed, latencyMs, buffered, prefetch, onToggle, onSeek, onSpeed } = props;
  const [jump, setJump] = useState('');
  const busy = state === 'loading';
  const playing = state === 'playing' || busy;
  const percent = total ? ((index + 1) / total) * 100 : 0;

  const submitJump = (event: React.FormEvent) => {
    event.preventDefault();
    const target = Number(jump);
    if (Number.isInteger(target) && target >= 1 && target <= total) {
      onSeek(target - 1);
      setJump('');
    }
  };

  return (
    <div className="player-controls">
      <div className="progress-wrapper">
        <div className="progress-info">
          <span>Câu {formatNumber(index + 1)} / {formatNumber(total)}</span>
          <span>{percent.toFixed(1)}%</span>
        </div>
        <div className="progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(percent)} aria-label="Tiến độ đọc">
          <div className="progress-fill" style={{ width: `${percent}%` }} />
        </div>
      </div>

      <div className="playback-buttons">
        <button className="ctrl-btn secondary" onClick={() => onSeek(0)} aria-label="Về câu đầu tiên" title="Về đầu"><SkipBack size={18} /></button>
        <button className="ctrl-btn secondary wide" onClick={() => onSeek(index - 1)} disabled={index <= 0}><ChevronLeft size={18} /> Câu trước</button>
        <button className="ctrl-btn primary" onClick={onToggle} aria-label={playing ? 'Tạm dừng' : 'Phát'} title="Space">
          {busy ? <Loader2 size={26} className="spin" /> : playing ? <Pause size={26} /> : <Play size={26} />}
        </button>
        <button className="ctrl-btn secondary wide" onClick={() => onSeek(index + 1)} disabled={index >= total - 1}>Câu sau <ChevronRight size={18} /></button>
        <button className="ctrl-btn secondary" onClick={() => onSeek(total - 1)} aria-label="Đến câu cuối cùng" title="Đến cuối"><SkipForward size={18} /></button>
      </div>

      <div className="options-row">
        <div className="segmented" role="radiogroup" aria-label="Tốc độ đọc">
          {SPEED_LEVELS.map((level) => (
            <button key={level} role="radio" aria-checked={speed === level} className={speed === level ? 'active' : ''} onClick={() => onSpeed(level)}>
              {level}x
            </button>
          ))}
        </div>
        <form className="jump-form" onSubmit={submitJump}>
          <label htmlFor="jump-input">Nhảy tới câu</label>
          <input id="jump-input" className="number-input" inputMode="numeric" value={jump} placeholder={String(index + 1)} onChange={(e) => setJump(e.target.value)} />
          <button className="btn-secondary small" type="submit">Đi</button>
        </form>
      </div>

      <p className="status-line" aria-live="polite">
        {STATE_TEXT[state]}
        {(state === 'playing' || state === 'loading') && ` · bộ đệm ${buffered}/${prefetch} · độ trễ ${latencyMs} ms`}
      </p>
    </div>
  );
};
