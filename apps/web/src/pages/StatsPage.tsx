import React, { useMemo, useState } from 'react';
import { fetchDaily, fetchMetrics } from '../api/analyticsApi.ts';
import { EmptyState, ErrorState, LoadingState } from '../components/common/StateViews.tsx';
import { BarChart } from '../components/Stats/BarChart.tsx';
import { useAsyncData } from '../hooks/useAsyncData.ts';
import { formatMinutes, formatNumber } from '../lib/format.ts';

const RANGES = { '7 ngày': 7, '30 ngày': 30, 'Tất cả': 365 } as const;
type RangeLabel = keyof typeof RANGES;
const WEEKDAYS = ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7'];

function dayLabel(isoDate: string, count: number): string {
  const [y, m, d] = isoDate.split('-').map(Number);
  const date = new Date(y, m - 1, d);
  return count <= 7 ? WEEKDAYS[date.getDay()] : `${String(d).padStart(2, '0')}/${String(m).padStart(2, '0')}`;
}

interface StatsPageProps {
  active: boolean;
}

/** S08 – Thống kê. All numbers are computed by the backend. */
export const StatsPage: React.FC<StatsPageProps> = ({ active }) => {
  const [range, setRange] = useState<RangeLabel>('7 ngày');
  const days = RANGES[range];
  const stats = useAsyncData(() => Promise.all([fetchDaily(days), fetchMetrics(days)]), [days, active], active);

  const [daily, metrics] = stats.data ?? [[], null];
  const totals = useMemo(
    () => ({ minutes: daily.reduce((a, d) => a + d.minutes, 0), words: daily.reduce((a, d) => a + d.words, 0), sessions: daily.reduce((a, d) => a + d.sessions, 0) }),
    [daily],
  );
  const labels = useMemo(() => daily.map((d) => dayLabel(d.date, daily.length)), [daily]);
  const minutes = useMemo(() => daily.map((d) => d.minutes), [daily]);
  const words = useMemo(() => daily.map((d) => d.words), [daily]);

  return (
    <div className="stats-page">
      <div className="segmented center" role="radiogroup" aria-label="Khoảng thời gian">
        {(Object.keys(RANGES) as RangeLabel[]).map((label) => (
          <button key={label} role="radio" aria-checked={range === label} className={range === label ? 'active' : ''} onClick={() => setRange(label)}>{label}</button>
        ))}
      </div>

      {stats.loading && !stats.data && <LoadingState />}
      {stats.error && <ErrorState message={stats.error} onRetry={stats.reload} />}

      {metrics && (
        <>
          <div className="metrics-grid">
            <Tile label="Tổng thời gian" value={formatMinutes(totals.minutes)} />
            <Tile label="Tổng số từ" value={formatNumber(totals.words)} />
            <Tile label="Tốc độ TB" value={`${Math.round(metrics.words_per_minute)} từ/ph`} />
            <Tile label="Tỷ lệ thành công" value={metrics.total_calls ? `${metrics.success_rate.toFixed(1)}%` : '—'} />
          </div>
          <p className="latency-line">
            {metrics.total_calls
              ? `Độ trễ API (ms): trung bình ${Math.round(metrics.avg_latency_ms)} · P95 ${Math.round(metrics.p95_latency_ms)} · lớn nhất ${Math.round(metrics.max_latency_ms)}`
              : 'Độ trễ API: chưa có dữ liệu'}
          </p>
          {totals.sessions === 0 ? (
            <EmptyState title="Chưa có dữ liệu đọc." hint="Hãy nghe một vài câu rồi quay lại." />
          ) : (
            <div className="charts-container">
              <BarChart title="Phút nghe theo ngày" labels={labels} values={minutes} color="#38bdf8" unit="phút" />
              <BarChart title="Số từ theo ngày" labels={labels} values={words} color="#10b981" unit="từ" />
            </div>
          )}
        </>
      )}
    </div>
  );
};

const Tile: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="metric-card">
    <span className="metric-label">{label}</span>
    <span className="metric-value">{value}</span>
  </div>
);
