import { apiGet } from './client.ts';
import { DailyStat, Metrics, VoiceStat } from '../types/analytics.ts';

export async function fetchDaily(days: number): Promise<DailyStat[]> {
  return apiGet<DailyStat[]>('/analytics/daily', { days });
}

export async function fetchMetrics(days: number): Promise<Metrics> {
  return apiGet<Metrics>('/analytics/metrics', { days });
}

export async function fetchVoiceStats(days: number): Promise<VoiceStat[]> {
  return apiGet<VoiceStat[]>('/analytics/voices', { days });
}
