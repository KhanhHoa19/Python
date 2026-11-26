import React, { useCallback, useEffect, useRef, useState } from 'react';
import { NotebookPen } from 'lucide-react';
import { fetchBookSentences } from '../api/booksApi.ts';
import { fetchBookmark } from '../api/playerApi.ts';
import { BookPickerDialog } from '../components/Dialogs/BookPickerDialog.tsx';
import { NoteDialog } from '../components/Dialogs/NoteDialog.tsx';
import { PlayerControls } from '../components/Reader/PlayerControls.tsx';
import { SentenceView } from '../components/Reader/SentenceView.tsx';
import { EmptyState, ErrorState, LoadingState } from '../components/common/StateViews.tsx';
import { ReaderTarget, useApp } from '../context/AppContext.tsx';
import { useAsyncData } from '../hooks/useAsyncData.ts';
import { useAudioPlayer } from '../hooks/useAudioPlayer.ts';
import { useReaderShortcuts } from '../hooks/useReaderShortcuts.ts';
import { SentenceSelection, readSentenceSelection, useTextSelection } from '../hooks/useTextSelection.ts';
import { VoiceOptions } from '../components/common/VoiceOptions.tsx';
import { BookSentence } from '../types/book.ts';
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
      const [sentences, bookmark] = await Promise.all([fetchBookSentences(target.bookId), fetchBookmark(target.bookId).catch(() => null)]);
      const saved = bookmark?.current_sentence_index ?? 0;
      const start = Math.min(Math.max(target.startIndex ?? saved, 0), Math.max(sentences.length - 1, 0));
      return { sentences, start };
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
          initialIndex={data.data.start}
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
  initialIndex: number;
  visible: boolean;
  onChangeBook: () => void;
}

const ReaderBody: React.FC<ReaderBodyProps> = ({ bookId, title, sentences, initialIndex, visible, onChangeBook }) => {
  const { settings, voices, voiceId, setVoiceId, openVoices, toast, showError } = useApp();
  const containerRef = useRef<HTMLDivElement>(null);
  const { selection, clear } = useTextSelection(containerRef);
  const [noteSelection, setNoteSelection] = useState<SentenceSelection | null>(null);

  const player = useAudioPlayer({
    bookId,
    sentences,
    initialIndex,
    voice: voiceId,
    prefetchCount: settings?.prefetch_count ?? 2,
    initialSpeed: settings?.default_speed ?? 1,
    onWarning: toast,
    onError: showError,
  });

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

  useReaderShortcuts({
    enabled: visible,
    onToggle: player.toggle,
    onNext: player.next,
    onPrevious: player.previous,
    onFaster: () => changeSpeed(1),
    onSlower: () => changeSpeed(-1),
    onNote: openNote,
  });

  return (
    <>
      <div className="reader-header">
        <h2 className="book-title">{title}</h2>
        <div className="reader-tools">
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
        <button className="btn-secondary" disabled={!selection} onMouseDown={(e) => e.preventDefault()} onClick={openNote} title="Phím tắt: N">
          <NotebookPen size={16} /> Ghi chú đoạn đã chọn
        </button>
      </div>

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
      />

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
