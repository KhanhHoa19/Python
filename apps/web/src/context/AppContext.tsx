import { createContext, useContext } from 'react';
import { Category } from '../types/book.ts';
import { AuthUser } from '../types/auth.ts';
import { ResolvedTheme } from '../hooks/useTheme.ts';
import { AppSettings } from '../types/settings.ts';
import { Voice, VoiceList } from '../types/voice.ts';

export type TabId = 'reader' | 'explore' | 'library' | 'quotes' | 'stats' | 'voices' | 'admin';

export interface ReaderTarget {
  bookId: number;
  title: string;
  /** Overrides the saved bookmark when set (e.g. "Đến câu này" from a note). */
  startIndex?: number;
  /** Changes on every request so re-opening the same book re-applies `startIndex`. */
  nonce: number;
}

export interface AppContextValue {
  /** The signed-in account. */
  user: AuthUser;
  logout: () => void;
  settings: AppSettings | null;
  categories: Category[];
  /** The category chosen in the sidebar (its slug), or null for all. Filters Khám phá and the shelf. */
  category: string | null;
  setCategory: (slug: string | null) => void;
  /** Light or dark, after resolving "follow the system" (charts read their colours for it). */
  theme: ResolvedTheme;
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
  /** Open Trích dẫn yêu thích, optionally limited to one book. */
  openQuotes: (bookId?: number) => void;
  openSettings: () => void;
  /** Open Kho Giọng Đọc. */
  openVoices: () => void;
  /** Replace the sidebar's category list (after an admin changed it). */
  refreshCategories: (categories: Category[]) => void;
}

export const AppContext = createContext<AppContextValue | null>(null);

export function useApp(): AppContextValue {
  const value = useContext(AppContext);
  if (!value) throw new Error('useApp must be used inside <AppContext.Provider>');
  return value;
}
