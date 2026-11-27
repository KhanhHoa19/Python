import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fetchCategories } from './api/booksApi.ts';
import { listVoices } from './api/voicesApi.ts';
import { getSettings } from './api/settingsApi.ts';
import { Sidebar } from './components/Sidebar/Sidebar.tsx';
import { SettingsDialog } from './components/Dialogs/SettingsDialog.tsx';
import { AppContext, AppContextValue, ReaderTarget, TabId } from './context/AppContext.tsx';
import { useLibrary } from './hooks/useLibrary.ts';
import { useTheme } from './hooks/useTheme.ts';
import { mostRecentUnfinished } from './lib/books.ts';
import { AdminPage } from './pages/AdminPage.tsx';
import { ExplorePage } from './pages/ExplorePage.tsx';
import { RecommendPage } from './pages/RecommendPage.tsx';
import { QuotesPage } from './pages/QuotesPage.tsx';
import { LibraryPage } from './pages/LibraryPage.tsx';
import { ReaderPage } from './pages/ReaderPage.tsx';
import { StatsPage } from './pages/StatsPage.tsx';
import { VoicesPage } from './pages/VoicesPage.tsx';
import { AuthUser } from './types/auth.ts';
import { Category } from './types/book.ts';
import { AppSettings } from './types/settings.ts';
import { VoiceList } from './types/voice.ts';

interface AppProps {
  user: AuthUser;
  onLogout: () => void;
}

export function App({ user, onLogout }: AppProps) {
  const [tab, setTab] = useState<TabId>('library');
  const [readerTarget, setReaderTarget] = useState<ReaderTarget | null>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [voiceList, setVoiceList] = useState<VoiceList | null>(null);
  const [voiceId, setVoiceIdState] = useState<string | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [quotesBook, setQuotesBook] = useState<number | null>(null);
  const [category, setCategoryState] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toastText, setToastText] = useState('');
  const toastTimer = useRef<number>();
  const nonce = useRef(0);
  const openQuotes = useCallback((bookId?: number) => {
    setQuotesBook(bookId ?? null);
    setTab('quotes');
  }, []);
  const resumed = useRef(false);

  const library = useLibrary();
  const theme = useTheme();

  const toast = useCallback((message: string) => {
    setToastText(message);
    window.clearTimeout(toastTimer.current);
    if (message) toastTimer.current = window.setTimeout(() => setToastText(''), 5000);
  }, []);

  const openInReader = useCallback((bookId: number, title: string, startIndex?: number) => {
    nonce.current += 1;
    setReaderTarget({ bookId, title, startIndex, nonce: nonce.current });
    setTab('reader');
  }, []);

  const refreshVoices = useCallback(async () => {
    const list = await listVoices();
    setVoiceList(list);
    setVoiceIdState((current) => (current && list.voices.some((v) => v.voice_id === current) ? current : list.voices[0]?.voice_id ?? current));
  }, []);

  const refreshSettings = useCallback(async () => {
    setSettings(await getSettings());
  }, []);

  const startup = useCallback(async () => {
    setError(null);
    const [settingsResult, voicesResult] = await Promise.allSettled([getSettings(), listVoices()]);
    if (settingsResult.status === 'fulfilled') {
      setSettings(settingsResult.value);
      setVoiceIdState(settingsResult.value.default_voice);
    }
    if (voicesResult.status === 'fulfilled') {
      const list = voicesResult.value;
      setVoiceList(list);
      setVoiceIdState((current) => (current && list.voices.some((v) => v.voice_id === current) ? current : list.voices[0]?.voice_id ?? current));
    }
    const failed = [settingsResult, voicesResult].find((r) => r.status === 'rejected') as PromiseRejectedResult | undefined;
    if (failed) setError(failed.reason instanceof Error ? failed.reason.message : 'Không kết nối được máy chủ.');
  }, []);

  useEffect(() => {
    void startup();
    void fetchCategories().then(setCategories).catch(() => undefined); // the sidebar list is optional
  }, [startup]);

  // First successful library load: go to the reader if a book was left unfinished.
  useEffect(() => {
    if (!library.loaded || resumed.current) return;
    resumed.current = true;
    const book = mostRecentUnfinished(library.books);
    if (book) openInReader(book.id, book.title);
  }, [library.loaded, library.books, openInReader]);

  // A rename in the library must also update the title shown in the reader (without reloading it).
  useEffect(() => {
    setReaderTarget((current) => {
      const book = current && library.books.find((b) => b.id === current.bookId);
      return current && book && book.title !== current.title ? { ...current, title: book.title } : current;
    });
  }, [library.books]);

  // Library data is refreshed whenever its tab is opened.
  const selectTab = useCallback(
    (next: TabId) => {
      setTab(next);
      if (next === 'library') void library.reload();
    },
    [library],
  );

  // The topic tag chosen on Khám phá or Kệ sách; both screens share it.
  const setCategory = setCategoryState;

  const retry = useCallback(() => {
    void startup();
    void library.reload();
  }, [startup, library]);

  const banner = error ?? (library.error && !library.loaded ? library.error : null);

  const value = useMemo<AppContextValue>(
    () => ({
      user,
      logout: onLogout,
      settings,
      categories,
      category,
      setCategory,
      theme: theme.resolved,
      voiceList,
      voices: voiceList?.voices ?? [],
      voiceId,
      setVoiceId: setVoiceIdState,
      refreshVoices,
      applySettings: setSettings,
      refreshSettings,
      toast,
      showError: setError,
      openInReader,
      goTo: selectTab,
      openQuotes,
      openSettings: () => setShowSettings(true),
      openVoices: () => selectTab('voices'),
      refreshCategories: setCategories,
    }),
    [user, onLogout, settings, categories, category, setCategory, openQuotes, theme.resolved, voiceList, voiceId, refreshVoices, refreshSettings, toast, openInReader, selectTab],
  );

  return (
    <AppContext.Provider value={value}>
      <div className="app-shell">
        <Sidebar
          current={tab}
          user={user}
          onLogout={onLogout}
          theme={theme.preference}
          onSelect={selectTab}
          onSettings={() => setShowSettings(true)}
          onToggleTheme={theme.cycle}
        />

        <div className="content">
        {banner && (
          <div className="banner-error" role="alert">
            <span>{banner}</span>
            <span>
              <button className="btn-secondary small" onClick={retry}>Thử lại</button>{' '}
              <button className="btn-secondary small" onClick={() => setError(null)} aria-label="Ẩn thông báo">✕</button>
            </span>
          </div>
        )}

        <main className="main-container">
          <section hidden={tab !== 'reader'} aria-label="Phòng Đọc"><ReaderPage target={readerTarget} visible={tab === 'reader'} /></section>
          <section hidden={tab !== 'explore'} aria-label="Khám Phá"><ExplorePage active={tab === 'explore'} library={library} /></section>
          <section hidden={tab !== 'recommend'} aria-label="Gợi Ý"><RecommendPage active={tab === 'recommend'} library={library} /></section>
          <section hidden={tab !== 'library'} aria-label="Kệ Sách Của Tôi"><LibraryPage library={library} active={tab === 'library'} /></section>
          <section hidden={tab !== 'quotes'} aria-label="Trích Dẫn Yêu Thích"><QuotesPage active={tab === 'quotes'} library={library} bookId={quotesBook} onBookChange={setQuotesBook} /></section>
          <section hidden={tab !== 'stats'} aria-label="Thống Kê"><StatsPage active={tab === 'stats'} /></section>
          <section hidden={tab !== 'voices'} aria-label="Kho Giọng Đọc"><VoicesPage active={tab === 'voices'} /></section>
          {user.role === 'admin' && <section hidden={tab !== 'admin'} aria-label="Quản Trị"><AdminPage active={tab === 'admin'} /></section>}
        </main>
        </div>

        <div className="toast" role="status" aria-live="polite">{toastText}</div>

        {showSettings && <SettingsDialog onClose={() => setShowSettings(false)} />}
      </div>
    </AppContext.Provider>
  );
}

export default App;
