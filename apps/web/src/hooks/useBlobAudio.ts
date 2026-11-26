import { useCallback, useEffect, useRef } from 'react';

/** Play one-off audio (voice preview, note replay). Starting a new clip stops the previous one. */
export function useBlobAudio() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);

  const stop = useCallback(() => {
    audioRef.current?.pause();
    audioRef.current = null;
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = null;
  }, []);

  const playBlob = useCallback(
    async (blob: Blob) => {
      stop();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      urlRef.current = url;
      audioRef.current = audio;
      audio.onended = stop;
      await audio.play();
    },
    [stop],
  );

  useEffect(() => stop, [stop]);
  return { playBlob, stop };
}
