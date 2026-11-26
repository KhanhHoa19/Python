import { createContext, useContext } from 'react';
import { AppSettings } from '../types/settings.ts';
import { Voice, VoiceList } from '../types/voice.ts';

export type TabId = 'reader' | 'library' | 'stats';

export interface ReaderTarget {
  bookId: number;
  title: string;
  /** Overrides the saved bookmark when set (e.g. "Đến câu này" from a note). */
  startIndex?: number;
  /** Changes on every request so re-opening the same book re-applies `startIndex`. */
  nonce: number;
}

export interface AppContextValue {
  settings: AppSettings | null;
  voiceList: VoiceList | null;
  voices: Voice[];
  voiceId: string | null;
  setVoiceId: (voiceId: string) => void;
  refreshVoices: () => Promise<void>;
  applySettings: (settings: AppSettings) => void;
  refreshSettings: () => Promise<void>;
  toast: (message: string) => void;
  showError: (message: string) => void;
  openInReader: (bookId: number, title: string, startIndex?: number) => void;
  goTo: (tab: TabId) => void;
  openSettings: () => void;
  openVoices: () => void;
}

export const AppContext = createContext<AppContextValue | null>(null);

export function useApp(): AppContextValue {
  const value = useContext(AppContext);
  if (!value) throw new Error('useApp must be used inside <AppContext.Provider>');
  return value;
}
