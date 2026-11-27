/** The short chime played when the story moves on to a new chapter (synthesised: no audio file to ship). */

export interface ChimeNote {
  /** Frequency in Hz and when the note starts, in seconds. */
  frequency: number;
  start: number;
}

export const CHIME_SECONDS = 1.6;
/** E5 then A5: a rising fourth, soft and unmistakable. */
export const CHIME_NOTES: readonly ChimeNote[] = [
  { frequency: 659.25, start: 0 },
  { frequency: 880, start: 0.28 },
];

/** Peak gain of a chime for a user volume of 0–1 (kept quiet: it must not startle someone who is nearly asleep). */
export function chimeGain(volume: number): number {
  return Math.min(Math.max(volume, 0), 1) * 0.35;
}

/** Play the chime and resolve when it has finished. Never rejects: a blocked audio context just skips the chime. */
export async function playChime(volume = 1): Promise<void> {
  try {
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    const context = new Ctx();
    await context.resume();
    const peak = chimeGain(volume);
    const now = context.currentTime;
    for (const note of CHIME_NOTES) {
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = 'sine';
      oscillator.frequency.value = note.frequency;
      gain.gain.setValueAtTime(0.0001, now + note.start);
      gain.gain.exponentialRampToValueAtTime(Math.max(peak, 0.0002), now + note.start + 0.03);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + CHIME_SECONDS);
      oscillator.connect(gain).connect(context.destination);
      oscillator.start(now + note.start);
      oscillator.stop(now + CHIME_SECONDS);
    }
    await new Promise<void>((resolve) => window.setTimeout(resolve, CHIME_SECONDS * 1000));
    void context.close();
  } catch {
    // no sound is better than a broken reader
  }
}

/** True when sentence `index` is the first of a chapter that follows the previous sentence's chapter (a continuous move, not a jump). */
export function startsNewChapter(sentences: { chapter_index: number }[], index: number): boolean {
  return index > 0 && index < sentences.length && sentences[index].chapter_index !== sentences[index - 1].chapter_index;
}
