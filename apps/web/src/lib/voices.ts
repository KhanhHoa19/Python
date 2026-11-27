import { Voice, VoiceList } from '../types/voice.ts';

/** 'Hoài My · Nữ · kể chuyện' style label for lists and dropdowns. */
export function describeVoice(voice: Voice): string {
  const gender = voice.gender === 'female' ? 'Nữ' : voice.gender === 'male' ? 'Nam' : '';
  const parts = [voice.display_name || voice.voice_id, gender, voice.style ?? ''];
  if (voice.is_custom) parts.push(voice.is_mine === false ? 'Giọng chung' : 'Giọng của tôi');
  return parts.filter(Boolean).join(' · ');
}

/** The voices of the studio: "system" = provider voices and public clones, "mine" = the user's own clones. */
export function splitVoices(voices: Voice[]): { system: Voice[]; mine: Voice[] } {
  return {
    system: voices.filter((v) => !v.is_custom || (v.is_public && !v.is_mine)),
    mine: voices.filter((v) => v.is_custom && v.is_mine),
  };
}

/** How many more voices the user may clone ("left" is null when there is no limit). */
export function cloneQuota(list: VoiceList | null): { used: number; max: number | null; left: number | null; full: boolean } {
  const used = list?.my_voice_count ?? 0;
  const max = list?.max_voices ?? null;
  const left = max === null ? null : Math.max(0, max - used);
  return { used, max, left, full: left === 0 };
}

/** The voice a new account starts with: the administrator's choice when it is still available. */
export function systemDefault(list: VoiceList | null): Voice | null {
  const id = list?.system_default_voice;
  return (id && list?.voices.find((v) => v.voice_id === id)) || null;
}
