import { apiGet, apiPost } from './client.ts';
import { NetworkHealth, VerifyResult } from '../types/health.ts';

export async function checkNetwork(): Promise<NetworkHealth> {
  return apiGet<NetworkHealth>('/health/network');
}

export async function verifyTts(): Promise<VerifyResult> {
  return apiPost<VerifyResult>('/tts/verify');
}
