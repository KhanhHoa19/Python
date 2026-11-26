import { useEffect } from 'react';

interface ShortcutHandlers {
  enabled: boolean;
  onToggle: () => void;
  onNext: () => void;
  onPrevious: () => void;
  onFaster: () => void;
  onSlower: () => void;
  onNote: () => void;
}

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName);
}

/** Space / ← → / ↑ ↓ / N while the reader is visible and no field has focus. */
export function useReaderShortcuts(handlers: ShortcutHandlers): void {
  const { enabled, onToggle, onNext, onPrevious, onFaster, onSlower, onNote } = handlers;
  useEffect(() => {
    if (!enabled) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (isTyping(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
      if (document.querySelector('[role="dialog"]')) return; // a dialog owns the keyboard
      const actions: Record<string, () => void> = {
        Space: onToggle,
        ArrowRight: onNext,
        ArrowLeft: onPrevious,
        ArrowUp: onFaster,
        ArrowDown: onSlower,
        KeyN: onNote,
      };
      const action = actions[event.code];
      if (action) {
        event.preventDefault();
        action();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [enabled, onToggle, onNext, onPrevious, onFaster, onSlower, onNote]);
}
