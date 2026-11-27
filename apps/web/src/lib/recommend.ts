/** Small pure helpers of the Gợi Ý tab (same options as apps/desktop/ui/viewmodels.py). */

export interface DurationOption {
  label: string;
  /** null = any length. */
  minutes: number | null;
}

export const DURATION_OPTIONS: readonly DurationOption[] = [
  { label: 'Bất kỳ', minutes: null },
  { label: '≤ 15 phút', minutes: 15 },
  { label: '≤ 30 phút', minutes: 30 },
  { label: '≤ 1 giờ', minutes: 60 },
  { label: '≤ 3 giờ', minutes: 180 },
];

/** Add the slug if missing, remove it if present (order of picking is kept). */
export function toggleSlug(list: string[], slug: string): string[] {
  return list.includes(slug) ? list.filter((s) => s !== slug) : [...list, slug];
}

/** "~25 phút", "~1 giờ", "~2 giờ 5 phút". */
export function formatDuration(minutes: number): string {
  if (minutes < 60) return `~${Math.max(1, minutes)} phút`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `~${hours} giờ` : `~${hours} giờ ${rest} phút`;
}

/** The summary line under the filters. */
export function describeFilters(moodLabel: string | null, duration: DurationOption): string {
  const parts = [moodLabel ? `tâm trạng ${moodLabel.toLowerCase()}` : '', duration.minutes ? duration.label : ''].filter(Boolean);
  return parts.length ? `Đang lọc: ${parts.join(', ')}` : '';
}
