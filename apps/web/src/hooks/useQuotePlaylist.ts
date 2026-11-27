import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchNoteAudio } from '../api/notesApi.ts';
import { stepIndex } from '../lib/quotes.ts';
import { Note } from '../types/note.ts';

/**
 * "Phát liên tục": plays the audio of a list of quotes one after another.
 * Starting anything else (a new playlist, a single quote) replaces what is playing; a quote whose audio cannot be
 * loaded is reported and skipped so one bad file does not end the playlist.
 */
export function useQuotePlaylist(onError: (message: string) => void) {
  const [queue, setQueue] = useState<Note[]>([]);
  const [index, setIndex] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);
  const generation = useRef(0);
  const queueRef = useRef<Note[]>([]);

  const release = useCallback(() => {
    audioRef.current?.pause();
    audioRef.current = null;
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = null;
  }, []);

  const stop = useCallback(() => {
    generation.current += 1;
    release();
    setIndex(null);
  }, [release]);

  const playAt = useCallback(
    async (position: number): Promise<void> => {
      const note = queueRef.current[position];
      if (!note) return stop();
      const mine = ++generation.current;
      release();
      setIndex(position);
      try {
        const url = URL.createObjectURL(await fetchNoteAudio(note.id));
        if (mine !== generation.current) return URL.revokeObjectURL(url);
        const audio = new Audio(url);
        urlRef.current = url;
        audioRef.current = audio;
        audio.onended = () => {
          const next = stepIndex(position, 1, queueRef.current.length);
          if (next === null) stop();
          else void playAt(next);
        };
        await audio.play();
      } catch (err) {
        if (mine !== generation.current) return;
        onError(err instanceof Error ? err.message : 'Không phát được trích dẫn.');
        const next = stepIndex(position, 1, queueRef.current.length);
        if (next === null) stop();
        else void playAt(next);
      }
    },
    [onError, release, stop],
  );

  const start = useCallback(
    (notes: Note[], from = 0) => {
      queueRef.current = notes;
      setQueue(notes);
      if (notes.length) void playAt(Math.min(Math.max(from, 0), notes.length - 1));
    },
    [playAt],
  );

  const step = useCallback(
    (direction: 1 | -1) => {
      if (index === null) return;
      const target = stepIndex(index, direction, queueRef.current.length);
      if (target === null) stop();
      else void playAt(target);
    },
    [index, playAt, stop],
  );

  useEffect(() => stop, [stop]);

  return { queue, index, current: index === null ? null : queue[index] ?? null, playing: index !== null, start, stop, next: () => step(1), previous: () => step(-1) };
}
