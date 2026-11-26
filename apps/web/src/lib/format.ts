/** Pure formatting helpers (no React, no DOM) so they can be unit-tested. */

/** Lowercase and strip Vietnamese diacritics so search ignores case and accents. */
export function normalizeText(value: string): string {
  return value
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();
}

export function parseIso(value: string | null | undefined): Date | null {
  if (!value) return null;
  // MySQL returns naive timestamps ("2026-11-26T04:37:53"); the backend writes UTC.
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(value);
  const date = new Date(hasZone ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

const pad = (n: number): string => String(n).padStart(2, '0');

/** dd/mm/yyyy HH:MM in local time, or an em dash when missing. */
export function formatDateTime(value: string | null | undefined): string {
  const d = parseIso(value);
  if (!d) return '—';
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** '12 giờ 40' for long durations, '35 phút' for short ones, '12 giây' under a minute. */
export function formatMinutes(minutes: number): string {
  if (minutes > 0 && minutes < 1) return `${Math.max(1, Math.round(minutes * 60))} giây`;
  const total = Math.round(minutes);
  const hours = Math.floor(total / 60);
  const mins = total % 60;
  return hours ? `${hours} giờ ${pad(mins)}` : `${mins} phút`;
}

/** Thousands separated by dots: 96200 -> '96.200'. */
export function formatNumber(value: number): string {
  return Math.round(value).toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}

/** m:ss for audio-like durations. */
export function formatClock(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  return `${Math.floor(total / 60)}:${pad(total % 60)}`;
}

/** 0..1 share of the daily character limit; 0 when unlimited. */
export function usageRatio(used: number, limit: number): number {
  return limit > 0 ? Math.min(used / limit, 1) : 0;
}
