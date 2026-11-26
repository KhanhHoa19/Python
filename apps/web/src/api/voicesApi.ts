import { apiDelete, apiGet, apiGetBlob, apiUpload } from './client.ts';
import { Voice, VoiceList } from '../types/voice.ts';

export async function listVoices(): Promise<VoiceList> {
  return apiGet<VoiceList>('/voices');
}

export async function cloneVoice(form: {
  sample: File;
  name: string;
  language: string;
  gender: 'male' | 'female';
  consent: boolean;
}): Promise<Voice> {
  const data = new FormData();
  data.append('sample', form.sample);
  data.append('name', form.name);
  data.append('language', form.language);
  data.append('gender', form.gender);
  data.append('consent', form.consent ? 'true' : 'false');
  return apiUpload<Voice>('/voices/clone', data);
}

export async function deleteVoice(voiceId: string): Promise<void> {
  await apiDelete(`/voices/${encodeURIComponent(voiceId)}`);
}

export async function fetchVoicePreview(voiceId: string): Promise<Blob> {
  return apiGetBlob(`/voices/${encodeURIComponent(voiceId)}/preview`);
}
