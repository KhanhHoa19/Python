import { apiGet, apiPut } from './client.ts';
import { AppSettings, SettingsUpdate } from '../types/settings.ts';

export async function getSettings(): Promise<AppSettings> {
  return apiGet<AppSettings>('/settings');
}

export async function updateSettings(settings: SettingsUpdate): Promise<AppSettings> {
  return apiPut<AppSettings>('/settings', settings);
}
