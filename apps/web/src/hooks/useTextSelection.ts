import { useCallback, useEffect, useState } from 'react';

export interface SentenceSelection {
  sentenceIndex: number;
  startOffset: number;
  endOffset: number;
  excerpt: string;
}

/** The element holding exactly one sentence's text (so offsets match the backend's sentence text). */
function sentenceElement(node: Node | null): HTMLElement | null {
  const element = node instanceof HTMLElement ? node : node?.parentElement ?? null;
  return element?.closest<HTMLElement>('[data-sentence-index]') ?? null;
}

/** Current browser selection, if it lies inside a single sentence of `container`. */
export function readSentenceSelection(container: HTMLElement | null): SentenceSelection | null {
  const selection = window.getSelection();
  if (!container || !selection || selection.rangeCount === 0 || selection.isCollapsed) return null;
  const range = selection.getRangeAt(0);
  const startEl = sentenceElement(range.startContainer);
  const endEl = sentenceElement(range.endContainer);
  if (!startEl || startEl !== endEl || !container.contains(startEl)) return null;

  const before = document.createRange();
  before.selectNodeContents(startEl);
  before.setEnd(range.startContainer, range.startOffset);
  const startOffset = before.toString().length;
  const excerpt = range.toString();
  if (!excerpt.trim()) return null;
  return {
    sentenceIndex: Number(startEl.dataset.sentenceIndex),
    startOffset,
    endOffset: startOffset + excerpt.length,
    excerpt,
  };
}

/** Tracks the selection so the "Ghi chú" button can enable itself. */
export function useTextSelection(container: React.RefObject<HTMLElement>) {
  const [selection, setSelection] = useState<SentenceSelection | null>(null);

  useEffect(() => {
    const update = () => setSelection(readSentenceSelection(container.current));
    document.addEventListener('selectionchange', update);
    return () => document.removeEventListener('selectionchange', update);
  }, [container]);

  const clear = useCallback(() => {
    window.getSelection()?.removeAllRanges();
    setSelection(null);
  }, []);

  return { selection, clear };
}
