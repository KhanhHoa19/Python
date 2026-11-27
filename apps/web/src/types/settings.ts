export interface SettingsUpdate {
  prefetch_count: number;
  default_speed: number;
  default_voice: string;
  daily_char_limit: number;
  /** Id of the background sound the user chose (0 = none), its volume (0–1) and the chapter chime. */
  ambient_track?: number;
  ambient_volume?: number;
  chapter_chime?: boolean;
}

export interface AppSettings extends SettingsUpdate {
  chars_used_today: number;
  provider: string;
}
