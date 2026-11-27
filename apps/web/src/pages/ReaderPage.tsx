import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ListTree, NotebookPen, Star } from 'lucide-react';
import { fetchBookChapters, fetchBookSentences } from '../api/booksApi.ts';
import { fetchBookmark } from '../api/playerApi.ts';
import { BookPickerDialog } from '../components/Dialogs/BookPickerDialog.tsx';
import { createNote, updateNote } from '../api/notesApi.ts';
import { EmotionChips } from '../components/common/EmotionChips.tsx';
import { NoteDialog } from '../components/Dialogs/NoteDialog.tsx';
import { ChapterListDialog } from '../components/Dialogs/ChapterListDialog.tsx';
import { listAmbient } from '../api/ambientApi.ts';
import { AmbientDialog } from '../components/Dialogs/AmbientDialog.tsx';
import { useAmbient } from '../hooks/useAmbient.ts';
import { playChime } from '../lib/chime.ts';
import { SleepTimerDialog } from '../components/Dialogs/SleepTimerDialog.tsx';
import { PlayerControls } from '../components/Reader/PlayerControls.tsx';
import { SentenceView } from '../components/Reader/SentenceView.tsx';
import { EmptyState, ErrorState, LoadingState } from '../components/common/StateViews.tsx';
import { ReaderTarget, useApp } from '../context/AppContext.tsx';
import { useAsyncData } from '../hooks/useAsyncData.ts';
import { useAudioPlayer } from '../hooks/useAudioPlayer.ts';
import { useReaderShortcuts } from '../hooks/useReaderShortcuts.ts';
import { SentenceSelection, readSentenceSelection, useTextSelection } from '../hooks/useTextSelection.ts';
import { VoiceOptions } from '../components/common/VoiceOptions.tsx';
import { chapterAt } from '../lib/chapters.ts';
import { BookSentence, Chapter } from '../types/book.ts';
import { sleepLabel } from '../lib/sleepTimer.ts';
import { EmotionTag, Note } from '../types/note.ts';
import { SPEED_LEVELS } from '../types/player.ts';

const ADD_VOICE = '__add_voice__';
export const PAUSE_EVENT = 'audiobook:pause';

interface ReaderPageProps {
  target: ReaderTarget | null;
  visible: boolean;
}

/** S03 – Phòng Đọc. Stays mounted while other tabs are shown so playback continues. */
export const ReaderPage: React.FC<ReaderPageProps> = ({ target, visible }) => {
  const { goTo, openInReader } = useApp();
  const [picking, setPicking] = useState(false);

  const data = useAsyncData(
    async () => {
      if (!target) return null;
      const [sentences, bookmark, chapters] = await Promise.all([
        fetchBookSentences(target.bookId),
        fetchBookmark(target.bookId).catch(() => null),
        fetchBookChapters(target.bookId).catch(() => []), // no table of contents is not a reason to refuse reading
      ]);
      const saved = bookmark?.current_sentence_index ?? 0;
      const start = Math.min(Math.max(target.startIndex ?? saved, 0), Math.max(sentences.length - 1, 0));
      return { sentences, chapters, start, savedVoice: bookmark?.voice ?? null };
    },
    [target?.bookId, target?.nonce],
    !!target,
  );

  return (
    <div className="reader-page">
      {!target && (
        <EmptyState title="Chưa chọn tài liệu." hint="Chọn một tài liệu để bắt đầu nghe.">
          <button className="btn-primary" onClick={() => setPicking(true)}>Đổi tài liệu</button>{' '}
          <button className="btn-secondary" onClick={() => goTo('library')}>Mở Thư viện</button>
        </EmptyState>
      )}
      {target && data.loading && <LoadingState text="Đang tải tài liệu…" />}
      {target && data.error && <ErrorState message={data.error} onRetry={data.reload} />}
      {target && data.data && !data.loading && (
        <ReaderBody
          key={`${target.bookId}:${target.nonce}`}
          bookId={target.bookId}
          title={target.title}
          sentences={data.data.sentences}
          chapters={data.data.chapters}
          initialIndex={data.data.start}
          savedVoice={data.data.savedVoice}
          visible={visible}
          onChangeBook={() => setPicking(true)}
        />
      )}
      {picking && (
        <BookPickerDialog
          onClose={() => setPicking(false)}
          onPick={(book) => {
            setPicking(false);
            openInReader(book.id, book.title);
          }}
        />
      )}
    </div>
  );
};

interface ReaderBodyProps {
  bookId: number;
  title: string;
  sentences: BookSentence[];
  chapters: Chapter[];
  initialIndex: number;
  savedVoice: string | null;
  visible: boolean;
  onChangeBook: () => void;
}

const ReaderBody: React.FC<ReaderBodyProps> = ({ bookId, title, sentences, chapters, initialIndex, savedVoice, visible, onChangeBook }) => {
  const { settings, voices, voiceId, setVoiceId, openVoices, openQuotes, toast, showError } = useApp();
  const containerRef = useRef<HTMLDivElement>(null);

  // Reopen the book with the voice it was last read with (if that voice still exists).
  const voiceRestored = useRef(false);
  useEffect(() => {
    if (voiceRestored.current || voices.length === 0) return; // once per opened book, after voices loaded
    voiceRestored.current = true;
    if (savedVoice && savedVoice !== voiceId && voices.some((v) => v.voice_id === savedVoice)) setVoiceId(savedVoice);
  }, [savedVoice, voices, voiceId, setVoiceId]);
  const { selection, clear } = useTextSelection(containerRef);
  const [sleepOpen, setSleepOpen] = useState(false);
  const [ambientOpen, setAmbientOpen] = useState(false);
  const ambientTracks = useAsyncData(listAmbient, [ambientOpen]);
  const [tocOpen, setTocOpen] = useState(false);
  const [savedQuote, setSavedQuote] = useState<Note | null>(null);
  const [noteSelection, setNoteSelection] = useState<SentenceSelection | null>(null);

  const player = useAudioPlayer({
    bookId,
    sentences,
    initialIndex,
    voice: voiceId,
    prefetchCount: settings?.prefetch_count ?? 2,
    initialSpeed: settings?.default_speed ?? 1,
    chapterChime: settings?.chapter_chime === false ? undefined : () => playChime(0.8),
    onWarning: toast,
    onError: showError,
  });

  // Background sound: plays under the voice while the reader plays, at its own volume.
  const ambientTrack = ambientTracks.data?.find((t) => t.id === (settings?.ambient_track ?? 0)) ?? null;
  useAmbient(ambientTrack?.url ?? null, settings?.ambient_volume ?? 0.4, player.state === 'playing' || player.state === 'loading');

  // Let other screens (e.g. note replay) pause the reader.
  useEffect(() => {
    window.addEventListener(PAUSE_EVENT, player.pause);
    return () => window.removeEventListener(PAUSE_EVENT, player.pause);
  }, [player.pause]);

  const openNote = useCallback(() => {
    const current = readSentenceSelection(containerRef.current);
    if (current) setNoteSelection(current);
    else toast('Hãy chọn một đoạn nằm trong cùng một câu.');
  }, [toast]);

  const changeSpeed = useCallback(
    (step: number) => {
      const levels = [...SPEED_LEVELS];
      const current = levels.reduce((best, level, i) => (Math.abs(level - player.speed) < Math.abs(levels[best] - player.speed) ? i : best), 0);
      player.setSpeed(levels[Math.min(Math.max(current + step, 0), levels.length - 1)]);
    },
    [player],
  );

  const currentChapter = chapterAt(chapters, player.index);

  // One tap saves the sentence being read as a favourite quote; the feeling chips below are optional.
  const bookmarkSentence = useCallback(async () => {
    try {
      setSavedQuote(await createNote({ book_id: bookId, sentence_index: player.index, voice: voiceId }));
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Không lưu được trích dẫn.');
    }
  }, [bookId, player.index, voiceId, showError]);

  const tagSavedQuote = useCallback(
    async (tag: EmotionTag | null) => {
      if (!savedQuote) return;
      try {
        setSavedQuote(await updateNote(savedQuote.id, { emotion_tag: tag }));
      } catch (err) {
        showError(err instanceof Error ? err.message : 'Không gắn được nhãn.');
      }
    },
    [savedQuote, showError],
  );

  // The tag bar disappears by itself (and stays a little longer after each tap on a chip).
  useEffect(() => {
    if (!savedQuote) return;
    const timer = window.setTimeout(() => setSavedQuote(null), 8000);
    return () => window.clearTimeout(timer);
  }, [savedQuote]);

  useReaderShortcuts({
    enabled: visible,
    onToggle: player.toggle,
    onNext: player.next,
    onPrevious: player.previous,
    onFaster: () => changeSpeed(1),
    onSlower: () => changeSpeed(-1),
    onNote: openNote,
    onBookmark: () => void bookmarkSentence(),
  });

  return (
    <>
      <div className="reader-header">
        <div>
          <p className="eyebrow">Đang đọc</p>
          <h1 className="book-title">{title}</h1>
        </div>
        <div className="reader-tools">
          {chapters.length > 1 && (
            <button className="btn-secondary" onClick={() => setTocOpen(true)}><ListTree size={16} /> Mục lục</button>
          )}
          <button className="btn-secondary" onClick={onChangeBook}>Đổi tài liệu</button>
          <label className="voice-picker">
            <span>Giọng</span>
            <select
              value={voiceId ?? ''}
              onChange={(e) => (e.target.value === ADD_VOICE ? openVoices() : setVoiceId(e.target.value))}
              aria-label="Giọng đọc"
            >
              <VoiceOptions voices={voices} extraValue={voiceId} />
              <option value={ADD_VOICE}>+ Thêm giọng mới…</option>
            </select>
          </label>
        </div>
      </div>

      {sentences.length === 0 ? (
        <EmptyState title="Tài liệu này chưa có câu nào." />
      ) : (
        <SentenceView
          sentences={sentences}
          currentIndex={player.index}
          visible={visible}
          containerRef={containerRef}
          onSentenceClick={player.seek}
        />
      )}

      <div className="note-row">
        {player.state === 'finished' && (
          <span className="finished-banner">
            Đã đọc xong. <button className="link-btn" onClick={() => player.seek(0)}>Đọc lại từ đầu</button>
          </span>
        )}
        <button className="btn-secondary" onClick={() => void bookmarkSentence()} disabled={sentences.length === 0} title="Phím tắt: B">
          <Star size={16} /> Đánh dấu đoạn này
        </button>
        <button className="btn-secondary" disabled={!selection} onMouseDown={(e) => e.preventDefault()} onClick={openNote} title="Phím tắt: N">
          <NotebookPen size={16} /> Trích đoạn đã chọn
        </button>
      </div>

      {savedQuote && (
        <div className="quote-saved" role="status">
          <span><Star size={15} /> Đã lưu đoạn này. Gắn nhãn:</span>
          <EmotionChips value={savedQuote.emotion_tag} onChange={(tag) => void tagSavedQuote(tag)} />
          <button className="link-btn" onClick={() => openQuotes(bookId)}>Xem trích dẫn</button>
        </div>
      )}

      <PlayerControls
        state={player.state}
        index={player.index}
        total={sentences.length}
        speed={player.speed}
        latencyMs={player.latencyMs}
        buffered={player.buffered}
        prefetch={settings?.prefetch_count ?? 2}
        onToggle={player.toggle}
        onSeek={player.seek}
        onSpeed={player.setSpeed}
        chapterTitle={chapters.length > 1 ? currentChapter?.title ?? '' : ''}
        sleepLabel={sleepLabel(player.sleep, player.sleepLeft)}
        sleepActive={player.sleep !== null}
        onSleep={() => setSleepOpen(true)}
        ambientLabel={ambientTrack ? ambientTrack.name : 'Nhạc nền'}
        ambientActive={ambientTrack !== null}
        onAmbient={() => setAmbientOpen(true)}
      />

      {tocOpen && (
        <ChapterListDialog
          chapters={chapters}
          currentChapter={currentChapter?.chapter_index ?? null}
          onPick={(chapter) => player.playFrom(chapter.start_sentence_index)}
          onClose={() => setTocOpen(false)}
        />
      )}
      {ambientOpen && <AmbientDialog tracks={ambientTracks.data ?? []} onClose={() => setAmbientOpen(false)} />}
      {sleepOpen && <SleepTimerDialog current={player.sleep} onSelect={player.setSleep} onClose={() => setSleepOpen(false)} />}
      {noteSelection && (
        <NoteDialog
          mode="create"
          bookId={bookId}
          selection={noteSelection}
          onClose={() => setNoteSelection(null)}
          onSaved={() => {
            setNoteSelection(null);
            clear();
            toast('Đã lưu ghi chú.');
          }}
        />
      )}
    </>
  );
};
