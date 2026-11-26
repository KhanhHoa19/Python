export interface Voice {
  voice_id: string;
  display_name: string;
  provider: string;
  language: string;
  gender: string | null;
  style: string | null;
  is_custom: boolean;
  consent_at: string | null;
}

export interface VoiceList {
  provider: string;
  supports_cloning: boolean;
  voices: Voice[];
  warning: string | null;
}
