import { Voice } from '../types/voice.ts';

/** 'Hoài My · Nữ · kể chuyện' style label for lists and dropdowns. */
export function describeVoice(voice: Voice): string {
  const gender = voice.gender === 'female' ? 'Nữ' : voice.gender === 'male' ? 'Nam' : '';
  const parts = [voice.display_name || voice.voice_id, gender, voice.style ?? ''];
  if (voice.is_custom) parts.push('Giọng của tôi');
  return parts.filter(Boolean).join(' · ');
}
