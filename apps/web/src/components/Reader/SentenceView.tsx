import React, { useEffect, useRef } from 'react';
import { BookSentence } from '../../types/book.ts';

/** Sentences rendered on each side of the current one (keeps the DOM small for long books). */
export const WINDOW_RADIUS = 60;

interface SentenceViewProps {
  sentences: BookSentence[];
  currentIndex: number;
  visible: boolean;
  containerRef: React.RefObject<HTMLDivElement>;
  onSentenceClick: (index: number) => void;
}

/** Karaoke-style text: the current sentence is highlighted, earlier ones are dimmed. */
export const SentenceView: React.FC<SentenceViewProps> = ({ sentences, currentIndex, visible, containerRef, onSentenceClick }) => {
  const activeRef = useRef<HTMLDivElement>(null);
  const lo = Math.max(0, currentIndex - WINDOW_RADIUS);
  const hi = Math.min(sentences.length - 1, currentIndex + WINDOW_RADIUS);

  useEffect(() => {
    if (!visible) return;
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    activeRef.current?.scrollIntoView({ block: 'center', behavior: reduce ? 'auto' : 'smooth' });
  }, [currentIndex, visible]);

  const handleClick = (index: number) => {
    // Dragging to select text must not count as a click-to-jump.
    if (window.getSelection()?.toString()) return;
    onSentenceClick(index);
  };

  const items: React.ReactNode[] = [];
  for (let i = lo; i <= hi; i++) {
    const state = i === currentIndex ? 'active' : i < currentIndex ? 'done' : '';
    items.push(
      <div
        key={sentences[i].sentence_index}
        ref={i === currentIndex ? activeRef : undefined}
        className={`sentence-item ${state}`}
        aria-current={i === currentIndex ? 'true' : undefined}
        onClick={() => handleClick(i)}
      >
        <span className="sentence-num" aria-hidden="true">{i + 1}</span>
        <span className="sentence-text" data-sentence-index={i}>{sentences[i].text_content}</span>
      </div>,
    );
  }

  return (
    <div className="sentence-list-container" ref={containerRef} aria-label="Nội dung tài liệu">
      {items}
    </div>
  );
};
