/** Sleep timer rules shared by the reader (same rules as apps/desktop/player/sleep_timer.py). */

export const FADE_SECONDS = 10;
export const CUSTOM_MINUTES_MAX = 600;
export const MINUTE_PRESETS = [15, 30, 45, 60] as const;

export type SleepSetting = { kind: 'minutes'; minutes: number } | { kind: 'chapter' };

/** Volume (0–1) when `remaining` seconds are left: 1 until the last `window` seconds, then a straight line to 0. */
export function fadeVolume(remaining: number, window: number = FADE_SECONDS): number {
  if (window <= 0 || remaining <= 0) return 0;
  if (remaining >= window) return 1;
  return remaining / window;
}

/** "12:30" for 750 seconds; rounds up so the display never shows 00:00 while there is still time. */
export function formatRemaining(seconds: number): string {
  const total = Math.max(0, Math.ceil(seconds));
  const minutes = Math.floor(total / 60);
  return `${String(minutes).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

/** True when sentence `index` is the last one of its chapter (or of the book). */
export function isLastOfChapter(sentences: { chapter_index: number }[], index: number): boolean {
  return index + 1 >= sentences.length || sentences[index + 1].chapter_index !== sentences[index].chapter_index;
}

/** Whole minutes from a text field, or null if it is not a number from 1 to CUSTOM_MINUTES_MAX. */
export function parseCustomMinutes(text: string): number | null {
  if (!/^\d+$/.test(text.trim())) return null;
  const value = Number(text);
  return value >= 1 && value <= CUSTOM_MINUTES_MAX ? value : null;
}

/** Text of the timer button in the player. */
export function sleepLabel(setting: SleepSetting | null, remainingSeconds: number | null): string {
  if (!setting) return 'Hẹn giờ';
  return setting.kind === 'chapter' ? 'Hết chương' : formatRemaining(remainingSeconds ?? setting.minutes * 60);
}
