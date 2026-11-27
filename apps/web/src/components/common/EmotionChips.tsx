import React from 'react';
import { EMOTIONS } from '../../lib/quotes.ts';
import { EmotionTag } from '../../types/note.ts';

interface EmotionChipsProps {
  value: EmotionTag | null;
  onChange: (tag: EmotionTag | null) => void;
  /** Add an "all" chip first (filters) instead of letting the chosen chip be clicked again to clear it (forms). */
  allLabel?: string;
}

/** The four feelings as toggle chips: one tap tags a quote, no typing needed. */
export const EmotionChips: React.FC<EmotionChipsProps> = ({ value, onChange, allLabel }) => (
  <div className="chip-row" role="group" aria-label="Nhãn cảm xúc">
    {allLabel && (
      <button type="button" className={`chip ${value === null ? 'selected' : ''}`} aria-pressed={value === null} onClick={() => onChange(null)}>{allLabel}</button>
    )}
    {EMOTIONS.map((e) => (
      <button key={e.value} type="button" className={`chip tag-${e.value} ${value === e.value ? 'selected' : ''}`} aria-pressed={value === e.value} onClick={() => onChange(!allLabel && value === e.value ? null : e.value)}>
        {e.label}
      </button>
    ))}
  </div>
);
