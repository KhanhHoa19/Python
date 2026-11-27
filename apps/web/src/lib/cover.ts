/** Placeholder book covers: a stable colour and initials derived from the title (no image needed). */

/** Stable hue (0–359) for a title; the same title always gets the same colour. */
export function coverHue(title: string): number {
  let hash = 0;
  for (const char of title.normalize('NFC')) hash = (hash * 31 + char.codePointAt(0)!) % 3600;
  return Math.round(hash / 10) % 360;
}

/** Up to two initials from the first words of a title ("Đắc Nhân Tâm" → "ĐN"). */
export function coverInitials(title: string): string {
  const words = title.trim().split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w));
  const letters = words.slice(0, 2).map((w) => (w.match(/[\p{L}\p{N}]/u)?.[0] ?? '').toUpperCase());
  return letters.join('') || '♪';
}
