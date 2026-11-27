import React, { useEffect, useRef } from 'react';
import { useApp } from '../../context/AppContext.tsx';
import { cssVar } from '../../hooks/useTheme.ts';
import { ArcElement, Chart, DoughnutController, Legend, PieController, Tooltip } from 'chart.js';

Chart.register(ArcElement, DoughnutController, PieController, Legend, Tooltip);

const PALETTE = ['--chart-1', '--chart-2', '--chart-3', '--chart-4', '--chart-5', '--chart-6'];

interface PieChartProps {
  title: string;
  labels: string[];
  values: number[];
  unit: string;
}

/** Chart.js pie chart; the canvas gets a text alternative listing every slice. */
export const PieChart: React.FC<PieChartProps> = ({ title, labels, values, unit }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { theme } = useApp();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const chart = new Chart(canvas, {
      type: 'pie',
      data: { labels, datasets: [{ data: values, backgroundColor: labels.map((_, i) => cssVar(PALETTE[i % PALETTE.length], '#f0a93e')), borderColor: cssVar('--surface', '#1c1916'), borderWidth: 2 }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? false : undefined,
        plugins: { legend: { position: 'bottom', labels: { color: cssVar('--text-2', '#c9c1b4'), boxWidth: 12, usePointStyle: true } } },
      },
    });
    return () => chart.destroy();
  }, [labels, values, theme]);

  const total = values.reduce((a, b) => a + b, 0);
  const summary = labels.map((label, i) => `${label} ${total ? Math.round((values[i] / total) * 100) : 0}%`).join(', ');
  return (
    <div className="chart-card">
      <h3 className="chart-title">{title}</h3>
      <div className="chart-canvas-wrapper">
        <canvas ref={canvasRef} role="img" aria-label={`${title}: ${summary} (tổng ${Math.round(total)} ${unit})`} />
      </div>
    </div>
  );
};
