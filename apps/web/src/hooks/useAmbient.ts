import { useEffect, useRef } from 'react';

/**
 * Background sound under the narration: one looping <audio> element, volume independent of the voice.
 * It plays while `active` (the reader is playing) and pauses otherwise, so pause, sleep timer and
 * end of book silence it too. `url` null = no sound.
 */
export function useAmbient(url: string | null, volume: number, active: boolean): void {
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (!url) return;
    const audio = new Audio(url);
    audio.loop = true;
    audio.preload = 'auto';
    audioRef.current = audio;
    return () => {
      audio.pause();
      audio.removeAttribute('src');
      audio.load();
      audioRef.current = null;
    };
  }, [url]);

  useEffect(() => {
    const audio = audioRef.current;
    if (audio) audio.volume = Math.min(Math.max(volume, 0), 1);
  }, [volume, url]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !url) return;
    if (active) void audio.play().catch(() => undefined); // blocked until the user's first click: the next Play retries
    else audio.pause();
  }, [active, url]);
}
