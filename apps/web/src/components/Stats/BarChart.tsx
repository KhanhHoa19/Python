import React, { useEffect, useRef } from 'react';
import { useApp } from '../../context/AppContext.tsx';
import { cssVar } from '../../hooks/useTheme.ts';
import { BarController, BarElement, CategoryScale, Chart, LinearScale, Tooltip } from 'chart.js';

Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip);

interface BarChartProps {
  title: string;
  labels: string[];
  values: number[];
  color: string;
  unit: string;
}

/** Chart.js bar chart; the canvas gets a text alternative summarising the data. */
export const BarChart: React.FC<BarChartProps> = ({ title, labels, values, color, unit }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<Chart | null>(null);
  const { theme } = useApp();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const chart = new Chart(canvas, {
      type: 'bar',
      data: { labels, datasets: [{ label: title, data: values, backgroundColor: cssVar(color, '#f0a93e'), borderRadius: 6 }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? false : undefined,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: cssVar('--muted', '#928a7c'), maxRotation: 45, autoSkip: true }, grid: { display: false } },
          y: { beginAtZero: true, ticks: { color: cssVar('--muted', '#928a7c') }, grid: { color: cssVar('--border', '#34302a') } },
        },
      },
    });
    chartRef.current = chart;
    return () => {
      chart.destroy();
      chartRef.current = null;
    };
  }, [title, labels, values, color, theme]);

  const total = values.reduce((a, b) => a + b, 0);
  return (
    <div className="chart-card">
      <h3 className="chart-title">{title}</h3>
      <div className="chart-canvas-wrapper">
        <canvas ref={canvasRef} role="img" aria-label={`${title}: tổng ${Math.round(total)} ${unit} trong ${labels.length} ngày`} />
      </div>
    </div>
  );
};
