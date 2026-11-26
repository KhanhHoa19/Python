import React from 'react';
import { describeVoice } from '../../lib/voices.ts';
import { Voice } from '../../types/voice.ts';

interface VoiceOptionsProps {
  voices: Voice[];
  /** A voice id that is selected but not in the list (e.g. a default from .env). */
  extraValue?: string | null;
}

/** <option>s grouped so Vietnamese voices come first and custom voices are easy to find. */
export const VoiceOptions: React.FC<VoiceOptionsProps> = ({ voices, extraValue }) => {
  const custom = voices.filter((v) => v.is_custom);
  const vietnamese = voices.filter((v) => !v.is_custom && v.language.toLowerCase().startsWith('vi'));
  const others = voices.filter((v) => !v.is_custom && !v.language.toLowerCase().startsWith('vi'));
  const known = voices.some((v) => v.voice_id === extraValue);
  const render = (list: Voice[]) => list.map((v) => <option key={v.voice_id} value={v.voice_id}>{describeVoice(v)}</option>);
  return (
    <>
      {extraValue && !known && <option value={extraValue}>{extraValue}</option>}
      {custom.length > 0 && <optgroup label="Giọng của tôi">{render(custom)}</optgroup>}
      {vietnamese.length > 0 && <optgroup label="Tiếng Việt">{render(vietnamese)}</optgroup>}
      {others.length > 0 && <optgroup label="Ngôn ngữ khác">{render(others)}</optgroup>}
    </>
  );
};
