import React, { useEffect, useRef } from 'react';
import { describeChapter } from '../../lib/chapters.ts';
import { formatNumber } from '../../lib/format.ts';
import { Chapter } from '../../types/book.ts';
import { Modal } from '../common/Modal.tsx';

interface ChapterListDialogProps {
  chapters: Chapter[];
  currentChapter: number | null;
  onPick: (chapter: Chapter) => void;
  onClose: () => void;
}

/** Mục lục: pick a chapter to start playing from its first sentence. */
export const ChapterListDialog: React.FC<ChapterListDialogProps> = ({ chapters, currentChapter, onPick, onClose }) => {
  const currentRef = useRef<HTMLLIElement>(null);
  useEffect(() => {
    currentRef.current?.scrollIntoView({ block: 'center' }); // no return value: an effect may only return a cleanup function
  }, []);

  return (
    <Modal title="Mục lục" onClose={onClose} width={560}>
      <ul className="chapter-list" aria-label="Danh sách chương">
        {chapters.map((chapter) => {
          const current = chapter.chapter_index === currentChapter;
          return (
            <li key={chapter.chapter_index} ref={current ? currentRef : undefined}>
              <button className={`chapter-item ${current ? 'current' : ''}`} aria-current={current ? 'true' : undefined} onClick={() => { onPick(chapter); onClose(); }}>
                <span className="chapter-title">{chapter.title}</span>
                <span className="chapter-meta">{describeChapter(chapter, formatNumber)}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </Modal>
  );
};
