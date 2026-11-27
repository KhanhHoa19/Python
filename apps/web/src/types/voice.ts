export interface Voice {
  voice_id: string;
  display_name: string;
  provider: string;
  language: string;
  gender: string | null;
  style: string | null;
  is_custom: boolean;
  consent_at: string | null;
  /** A cloned voice shared with everyone by an administrator. */
  is_public?: boolean;
  /** A voice the signed-in user cloned. */
  is_mine?: boolean;
}

export interface VoiceList {
  provider: string;
  supports_cloning: boolean;
  /** [min, max] seconds of audio the provider accepts as a cloning sample. */
  clone_sample_seconds: [number, number];
  voices: Voice[];
  warning: string | null;
  /** How many voices the user cloned, and how many they may keep (null = unlimited, for admins). */
  my_voice_count?: number;
  max_voices?: number | null;
  /** The voice everyone starts with, chosen by an administrator ('' = the one from the server settings). */
  system_default_voice?: string;
}
