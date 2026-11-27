import React, { useEffect, useState } from 'react';
import { Download } from 'lucide-react';
import { cancelExport, downloadExport, estimateExport, getExportJob, startExport } from '../../api/exportApi.ts';
import { formatNumber } from '../../lib/format.ts';
import { Book } from '../../types/book.ts';
import { ExportEstimate, ExportJob } from '../../types/export.ts';
import { useApp } from '../../context/AppContext.tsx';
import { Modal } from '../common/Modal.tsx';

interface ExportDialogProps {
  book: Book;
  onClose: () => void;
}

/** S07 – Xuất audio. */
export const ExportDialog: React.FC<ExportDialogProps> = ({ book, onClose }) => {
  const { voiceId } = useApp();
  const [mode, setMode] = useState<'all' | 'range'>('all');
  const [from, setFrom] = useState('1');
  const [to, setTo] = useState(String(book.total_sentences));
  const [estimate, setEstimate] = useState<ExportEstimate | null>(null);
  const [estimateError, setEstimateError] = useState<string | null>(null);
  const [job, setJob] = useState<ExportJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  const range = (): { from: number; to: number | null } | null => {
    if (mode === 'all') return { from: 0, to: null };
    const start = Number(from);
    const end = Number(to);
    if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end < start) return null;
    return { from: start - 1, to: end - 1 };
  };

  useEffect(() => {
    const r = range();
    setEstimate(null);
    if (!r) return setEstimateError('Khoảng câu không hợp lệ.');
    setEstimateError(null);
    let active = true;
    estimateExport(book.id, r.from, r.to, voiceId)
      .then((value) => active && setEstimate(value))
      .catch((err: Error) => active && setEstimateError(err.message));
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, from, to, book.id, voiceId]);

  // Poll the running job.
  useEffect(() => {
    if (!job || job.status !== 'running') return;
    const timer = window.setTimeout(() => {
      getExportJob(job.job_id).then(setJob).catch((err: Error) => setError(err.message));
    }, 800);
    return () => window.clearTimeout(timer);
  }, [job]);

  const start = async () => {
    const r = range();
    if (!r) return;
    setError(null);
    try {
      setJob(await startExport(book.id, { from_index: r.from, to_index: r.to, voice: voiceId }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không bắt đầu xuất được.');
    }
  };

  const [cancelling, setCancelling] = useState(false);
  useEffect(() => setCancelling(false), [job?.job_id]);
  const cancel = async () => {
    if (!job) return;
    setCancelling(true);
    try {
      await cancelExport(job.job_id);
    } catch (err) {
      setCancelling(false);
      setError(err instanceof Error ? err.message : 'Không hủy được.');
    }
  };

  const [saving, setSaving] = useState(false);
  const save = async (finished: ExportJob) => {
    setSaving(true);
    try {
      const url = URL.createObjectURL(await downloadExport(finished.job_id));
      const link = document.createElement('a');
      link.href = url;
      link.download = finished.file_name ?? 'audiobook';
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được file.');
    } finally {
      setSaving(false);
    }
  };

  const running = job?.status === 'running';
  const overLimit = !!estimate && estimate.daily_limit > 0 && estimate.chars_used_today + estimate.chars_to_synthesize > estimate.daily_limit;

  return (
    <Modal title={`Xuất audio – ${book.title}`} onClose={onClose} width={560}>
      <div className="modal-form">
        <fieldset className="form-group" disabled={running}>
          <legend className="field-label">Phạm vi</legend>
          <label className="radio-row"><input type="radio" checked={mode === 'all'} onChange={() => setMode('all')} /> Cả tài liệu</label>
          <div className="radio-row">
            <input type="radio" id="range-mode" checked={mode === 'range'} onChange={() => setMode('range')} />
            <label htmlFor="range-mode">Từ câu</label>
            <input className="number-input" aria-label="Từ câu" value={from} onChange={(e) => (setMode('range'), setFrom(e.target.value))} />
            <span>đến câu</span>
            <input className="number-input" aria-label="Đến câu" value={to} onChange={(e) => (setMode('range'), setTo(e.target.value))} />
          </div>
        </fieldset>

        <p className="status-text" aria-live="polite">
          {estimateError && <span className="error">{estimateError}</span>}
          {!estimateError && !estimate && 'Đang ước tính…'}
          {estimate && (
            <>
              ~ {formatNumber(estimate.sentences)} câu · ~ {Math.round(estimate.estimated_minutes)} phút ·{' '}
              {formatNumber(estimate.chars_to_synthesize)} ký tự cần gọi API ({formatNumber(estimate.chars_cached)} lấy từ cache)
            </>
          )}
        </p>
        {overLimit && <p className="status-text warn">Vượt giới hạn ký tự hôm nay: chỉ xuất được phần đã có trong cache.</p>}

        {job && (
          <div>
            <progress className="progress-native" value={job.done} max={Math.max(job.total, 1)} aria-label="Tiến trình xuất" />
            <p className="muted">{job.done} / {job.total} câu</p>
            {job.status === 'done' && <p className="status-text ok">✔ Hoàn tất. {job.file_name}</p>}
            {job.status === 'cancelled' && <p className="status-text warn">Đã hủy xuất. Phần đã tổng hợp vẫn nằm trong cache.</p>}
            {job.status === 'failed' && <p className="status-text error" role="alert">Xuất thất bại: {job.error}</p>}
          </div>
        )}
        {error && <p className="status-text error" role="alert">{error}</p>}

        <div className="modal-actions">
          <button className="btn-secondary" onClick={onClose}>Đóng</button>
          {job?.status === 'done' ? (
            <button className="btn-primary" onClick={() => void save(job)} disabled={saving}>
              <Download size={16} /> {saving ? 'Đang tải…' : 'Tải về'}
            </button>
          ) : (
            <>
              {running && <button className="btn-secondary" onClick={cancel} disabled={cancelling}>{cancelling ? 'Đang hủy…' : 'Hủy xuất'}</button>}
              <button className="btn-primary" onClick={start} disabled={running || !range()}>Bắt đầu xuất</button>
            </>
          )}
        </div>
      </div>
    </Modal>
  );
};
