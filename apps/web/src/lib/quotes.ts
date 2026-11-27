import { EmotionTag, Note } from '../types/note.ts';
import { normalizeText } from './format.ts';

/** The feelings a quote can carry, in the order shown. The same four (and labels) exist in the desktop app. */
export const EMOTIONS: { value: EmotionTag; label: string }[] = [
  { value: 'inspiring', label: 'Truyền cảm hứng' },
  { value: 'touching', label: 'Chạm cảm xúc' },
  { value: 'wise', label: 'Triết lý hay' },
  { value: 'funny', label: 'Hài hước' },
];

export function emotionLabel(tag: EmotionTag | null | undefined): string {
  return EMOTIONS.find((e) => e.value === tag)?.label ?? '';
}

/** Text search inside the quotes already on screen (accents and case ignored). */
export function matchesQuote(note: Note, query: string): boolean {
  const needle = normalizeText(query.trim());
  return !needle || normalizeText(`${note.excerpt} ${note.note_text} ${note.book_title}`).includes(needle);
}

/** Playlist position after a step: stays inside 0..total-1, or null when it ran off the end / the start. */
export function stepIndex(index: number, step: 1 | -1, total: number): number | null {
  const next = index + step;
  return next >= 0 && next < total ? next : null;
}

/** "2 / 7" shown while a playlist plays. */
export function playlistProgress(index: number | null, total: number): string {
  return index === null ? '' : `${index + 1} / ${total}`;
}
