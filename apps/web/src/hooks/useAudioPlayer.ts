import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '../api/client.ts';
import { fetchSentenceAudio, recordReadingSession, saveBookmark } from '../api/playerApi.ts';
import { AudioPrefetcher } from '../lib/audioPrefetcher.ts';
import { startsNewChapter } from '../lib/chime.ts';
import { FADE_SECONDS, SleepSetting, fadeVolume, isLastOfChapter } from '../lib/sleepTimer.ts';
import { BookSentence } from '../types/book.ts';
import { PlayerState } from '../types/player.ts';

const BOOKMARK_INTERVAL_MS = 5000;

export interface UseAudioPlayerOptions {
  bookId: number;
  sentences: BookSentence[];
  initialIndex: number;
  voice: string | null;
  /** Voice of the dialogue (multi-voice narration); null/'' = the narrator reads everything. */
  characterVoice?: string | null;
  prefetchCount: number;
  initialSpeed: number;
  /** Played (and awaited) before the first sentence of a new chapter when playback moves on by itself. */
  chapterChime?: () => Promise<void>;
  onWarning: (message: string) => void;
  onError: (message: string) => void;
}

interface Session {
  start: Date;
  seconds: number;
  sentences: number;
  words: number;
  voice: string | null; // a session belongs to one voice
}

/**
 * IMPORTANT: mount with `key={bookId}`. The cleanup effects flush progress for the book the hook was
 * created with; switching books inside one mounted instance would attribute it to the wrong book.
 *
 * Sentence-by-sentence playback: one <audio> element, a bounded look-ahead buffer of Blob URLs,
 * speed applied with playbackRate (so the cache is shared across speeds), bookmark + session reporting.
 */
export function useAudioPlayer(options: UseAudioPlayerOptions) {
  const { bookId, sentences, voice, prefetchCount } = options;
  const characterVoice = options.characterVoice || null;
  const [index, setIndex] = useState(options.initialIndex);
  const [state, setState] = useState<PlayerState>('idle');
  const [speed, setSpeedState] = useState(options.initialSpeed);
  const [latencyMs, setLatencyMs] = useState(0);
  const [buffered, setBuffered] = useState(0);

  // Latest values for event handlers (avoids stale closures).
  const live = useRef({ ...options, index, state, speed });
  live.current = { ...options, index, state, speed };

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const prefetcherRef = useRef<AudioPrefetcher | null>(null);
  const generation = useRef(0);
  const loadedIndex = useRef<number | null>(null);
  const session = useRef<Session | null>(null);
  const lastBookmarkAt = useRef(0);

  // Sleep timer: the countdown only runs while playing; see lib/sleepTimer.ts for the rules.
  const [sleep, setSleepState] = useState<SleepSetting | null>(null);
  const [sleepLeft, setSleepLeft] = useState<number | null>(null);
  const sleepRef = useRef<{ setting: SleepSetting; remaining: number; last: number } | null>(null);

  const setSleep = useCallback((setting: SleepSetting | null) => {
    if (audioRef.current) audioRef.current.volume = 1; // cancelling (or re-arming) always restores the volume
    const seconds = setting?.kind === 'minutes' ? setting.minutes * 60 : 0;
    sleepRef.current = setting ? { setting, remaining: seconds, last: performance.now() } : null;
    setSleepState(setting);
    setSleepLeft(setting?.kind === 'minutes' ? seconds : null);
  }, []);

  const total = sentences.length;

  // ---- reporting -------------------------------------------------------------------------

  const saveProgress = useCallback((at: number, keepalive = false) => {
    const current = live.current.sentences;
    if (!current.length) return;
    const i = Math.min(Math.max(at, 0), current.length - 1);
    void saveBookmark(
      {
        book_id: live.current.bookId,
        current_chapter: current[i].chapter_index || 1,
        current_sentence_index: i,
        completion_percentage: Number((((i + 1) / current.length) * 100).toFixed(1)),
        voice: live.current.voice,
      },
      keepalive,
    ).catch(() => undefined);
  }, []);

  const flushSession = useCallback((keepalive = false) => {
    const s = session.current;
    session.current = null;
    if (!s || s.sentences === 0) return;
    void recordReadingSession(
      {
        book_id: live.current.bookId,
        start_time: s.start.toISOString(),
        end_time: new Date().toISOString(),
        duration_seconds: Math.max(1, Math.round(s.seconds)),
        sentences_read: s.sentences,
        words_read: s.words,
        voice: s.voice,
      },
      keepalive,
    ).catch(() => undefined);
  }, []);

  // ---- playback --------------------------------------------------------------------------

  const stopAudio = useCallback(() => {
    generation.current += 1;
    audioRef.current?.pause();
  }, []);

  const finishWithError = useCallback(
    (error: unknown) => {
      stopAudio();
      setState('paused');
      flushSession();
      saveProgress(live.current.index);
      const message = error instanceof ApiError ? error.message : 'Không phát được âm thanh.';
      live.current.onError(message);
    },
    [flushSession, saveProgress, stopAudio],
  );

  const playIndex = useCallback(
    async (target: number): Promise<void> => {
      const prefetcher = prefetcherRef.current;
      const audio = audioRef.current;
      if (!prefetcher || !audio || target < 0 || target >= live.current.sentences.length) return;

      const gen = ++generation.current;
      audio.pause();
      setIndex(target);
      setState('loading');
      const startedAt = performance.now();

      let url: string;
      try {
        url = await prefetcher.get(target);
      } catch (error) {
        if (gen !== generation.current) return; // superseded by a seek / pause
        if (error instanceof ApiError && !error.isQuotaError && !error.isConnectionError) {
          live.current.onWarning(`Bỏ qua câu ${target + 1} (lỗi TTS: ${error.message})`);
          if (target + 1 < live.current.sentences.length) return playIndex(target + 1);
          setState('finished');
          return;
        }
        finishWithError(error);
        return;
      }
      if (gen !== generation.current) return;

      if (!session.current) session.current = { start: new Date(), seconds: 0, sentences: 0, words: 0, voice: live.current.voice };
      audio.src = url;
      loadedIndex.current = target;
      audio.defaultPlaybackRate = live.current.speed;
      audio.playbackRate = live.current.speed;
      try {
        await audio.play();
      } catch (error) {
        if (gen !== generation.current) return;
        setState('paused');
        live.current.onError(
          error instanceof DOMException && error.name === 'NotAllowedError'
            ? 'Trình duyệt chặn tự phát. Bấm ▶ để bắt đầu.'
            : 'Không phát được âm thanh.',
        );
        return;
      }
      if (gen !== generation.current) return;

      setState('playing');
      setLatencyMs(Math.round(performance.now() - startedAt));
      prefetcher.warm(target + 1);
      const now = Date.now();
      if (now - lastBookmarkAt.current >= BOOKMARK_INTERVAL_MS) {
        lastBookmarkAt.current = now;
        saveProgress(target);
      }
    },
    [finishWithError, saveProgress],
  );

  // One <audio> element for the lifetime of the hook.
  useEffect(() => {
    const audio = new Audio();
    audio.preload = 'auto';
    audioRef.current = audio;

    const onEnded = () => {
      const i = loadedIndex.current;
      if (i === null) return;
      const s = session.current;
      if (s) {
        s.sentences += 1;
        s.words += live.current.sentences[i]?.word_count ?? 0;
        s.seconds += Number.isFinite(audio.duration) ? audio.duration / (audio.playbackRate || 1) : 0;
      }
      if (sleepRef.current?.setting.kind === 'chapter' && isLastOfChapter(live.current.sentences, i)) {
        // "Dừng khi hết chương này": stop on the first sentence of the next chapter, ready to resume.
        const more = i + 1 < live.current.sentences.length;
        loadedIndex.current = null;
        if (more) setIndex(i + 1);
        setState(more ? 'paused' : 'finished');
        flushSession();
        saveProgress(more ? i + 1 : i);
        setSleep(null);
        live.current.onWarning('Đã dừng hết chương theo hẹn giờ.');
        return;
      }
      if (i + 1 < live.current.sentences.length) {
        const chime = live.current.chapterChime;
        if (chime && startsNewChapter(live.current.sentences, i + 1)) {
          void chime().then(() => {
            if (live.current.state === 'playing' && loadedIndex.current === i) void playIndex(i + 1); // not paused or moved meanwhile
          });
        } else {
          void playIndex(i + 1);
        }
      } else {
        setState('finished');
        flushSession();
        saveProgress(i);
      }
    };
    audio.addEventListener('ended', onEnded);

    return () => {
      audio.removeEventListener('ended', onEnded);
      audio.pause();
      audio.removeAttribute('src');
      audioRef.current = null;
    };
  }, [flushSession, playIndex, saveProgress, setSleep]);

  // Rebuild the buffer when the book or voice changes; never reuse audio from another voice.
  useEffect(() => {
    const prefetcher = new AudioPrefetcher(
      (i, signal) => fetchSentenceAudio(bookId, i, voice, signal, characterVoice),
      total,
      prefetchCount,
    );
    prefetcherRef.current = prefetcher;
    return () => {
      prefetcher.reset();
      prefetcherRef.current = null;
    };
  }, [bookId, voice, characterVoice, total, prefetchCount]);

  // A voice change while playing restarts the current sentence with the new voice.
  const voiceKey = `${voice ?? ''}|${characterVoice ?? ''}`; // narrator and character voice: a change of either restarts the sentence
  const previousVoice = useRef(voiceKey);
  useEffect(() => {
    if (previousVoice.current !== voiceKey) {
      previousVoice.current = voiceKey;
      flushSession();
      if (live.current.state === 'playing' || live.current.state === 'loading') {
        void playIndex(live.current.index);
      }
    }
  }, [voiceKey, playIndex, flushSession]);

  // New book: stop everything and move to its start position.
  useEffect(() => {
    stopAudio();
    loadedIndex.current = null;
    setState('idle');
    setIndex(Math.min(Math.max(options.initialIndex, 0), Math.max(total - 1, 0)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId, options.initialIndex]);

  // Buffer indicator while playing.
  useEffect(() => {
    if (state !== 'playing' && state !== 'loading') return;
    const timer = window.setInterval(() => {
      setBuffered(prefetcherRef.current?.readyAhead(live.current.index) ?? 0);
    }, 500);
    return () => window.clearInterval(timer);
  }, [state]);

  // Flush on unmount and when the tab/page is closed.
  useEffect(() => {
    const onPageHide = () => {
      flushSession(true);
      saveProgress(live.current.index, true);
    };
    window.addEventListener('pagehide', onPageHide);
    return () => {
      window.removeEventListener('pagehide', onPageHide);
      flushSession(true);
      saveProgress(live.current.index, true);
    };
  }, [bookId, flushSession, saveProgress]);

  // ---- public controls -------------------------------------------------------------------

  const pause = useCallback(() => {
    if (live.current.state !== 'playing' && live.current.state !== 'loading') return;
    stopAudio();
    setState('paused');
    flushSession();
    saveProgress(live.current.index);
  }, [flushSession, saveProgress, stopAudio]);

  // Countdown, fade-out and the pause when time is up.
  useEffect(() => {
    if (!sleep) return;
    const timer = window.setInterval(() => {
      const state = sleepRef.current;
      const audio = audioRef.current;
      if (!state || !audio) return;
      const now = performance.now();
      const elapsed = (now - state.last) / 1000;
      state.last = now;
      const playing = live.current.state === 'playing';
      if (state.setting.kind === 'minutes') {
        if (playing) state.remaining -= elapsed;
        audio.volume = fadeVolume(state.remaining);
        setSleepLeft(Math.max(0, state.remaining));
        if (state.remaining <= 0) {
          pause();
          setSleep(null); // restores the volume for the next listen
          live.current.onWarning('Hết giờ hẹn: đã tạm dừng.');
        }
      } else if (playing && isLastOfChapter(live.current.sentences, live.current.index) && audio.duration > 0) {
        const rate = audio.playbackRate || 1;
        const length = audio.duration / rate;
        audio.volume = fadeVolume(length - audio.currentTime / rate, Math.min(FADE_SECONDS, length));
      } else {
        audio.volume = 1;
      }
    }, 200);
    return () => window.clearInterval(timer);
  }, [sleep, pause, setSleep]);

  const play = useCallback(() => {
    const audio = audioRef.current;
    if (!total) return;
    if (live.current.state === 'paused' && audio && loadedIndex.current === live.current.index && audio.src) {
      generation.current += 1;
      if (!session.current) session.current = { start: new Date(), seconds: 0, sentences: 0, words: 0, voice: live.current.voice };
      audio
        .play()
        .then(() => setState('playing'))
        .catch(() => void playIndex(live.current.index));
      return;
    }
    void playIndex(live.current.index);
  }, [playIndex, total]);

  const toggle = useCallback(() => {
    const s = live.current.state;
    if (s === 'playing' || s === 'loading') pause();
    else play();
  }, [pause, play]);

  const seek = useCallback(
    (target: number) => {
      if (!total) return;
      const clamped = Math.min(Math.max(target, 0), total - 1);
      const s = live.current.state;
      if (s === 'playing' || s === 'loading') {
        void playIndex(clamped);
      } else {
        stopAudio();
        loadedIndex.current = null;
        setIndex(clamped);
        if (s === 'finished') setState('paused');
        saveProgress(clamped);
      }
    },
    [playIndex, saveProgress, stopAudio, total],
  );

  /** Jump to a sentence and start playing there (chapter list): old audio is dropped, playback starts at once. */
  const playFrom = useCallback(
    (target: number) => {
      if (!total) return;
      void playIndex(Math.min(Math.max(target, 0), total - 1));
    },
    [playIndex, total],
  );

  const next = useCallback(() => seek(live.current.index + 1), [seek]);
  const previous = useCallback(() => seek(live.current.index - 1), [seek]);

  const setSpeed = useCallback((value: number) => {
    setSpeedState(value);
    live.current.speed = value;
    const audio = audioRef.current;
    if (audio) {
      audio.defaultPlaybackRate = value;
      audio.playbackRate = value;
    }
  }, []);

  return { index, state, speed, latencyMs, buffered, sleep, sleepLeft, setSleep, toggle, play, pause, seek, playFrom, next, previous, setSpeed };
}
