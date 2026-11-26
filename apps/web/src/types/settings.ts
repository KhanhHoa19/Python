export interface SettingsUpdate {
  prefetch_count: number;
  default_speed: number;
  default_voice: string;
  daily_char_limit: number;
}

export interface AppSettings extends SettingsUpdate {
  chars_used_today: number;
  provider: string;
}
