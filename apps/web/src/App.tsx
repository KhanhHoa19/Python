import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { listVoices } from './api/voicesApi.ts';
import { getSettings } from './api/settingsApi.ts';
import { Navbar } from './components/Navbar/Navbar.tsx';
import { SettingsDialog } from './components/Dialogs/SettingsDialog.tsx';
import { VoicesDialog } from './components/Dialogs/VoicesDialog.tsx';
import { AppContext, AppContextValue, ReaderTarget, TabId } from './context/AppContext.tsx';
import { useLibrary } from './hooks/useLibrary.ts';
import { mostRecentUnfinished } from './lib/books.ts';
import { LibraryPage } from './pages/LibraryPage.tsx';
import { ReaderPage } from './pages/ReaderPage.tsx';
import { StatsPage } from './pages/StatsPage.tsx';
import { AppSettings } from './types/settings.ts';
import { VoiceList } from './types/voice.ts';

export function App() {
  const [tab, setTab] = useState<TabId>('library');
  const [readerTarget, setReaderTarget] = useState<ReaderTarget | null>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [voiceList, setVoiceList] = useState<VoiceList | null>(null);
  const [voiceId, setVoiceIdState] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showVoices, setShowVoices] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toastText, setToastText] = useState('');
  const toastTimer = useRef<number>();
  const nonce = useRef(0);
  const resumed = useRef(false);

  const library = useLibrary();

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
  }, [startup]);

  // First successful library load: go to the reader if a book was left unfinished.
  useEffect(() => {
    if (!library.loaded || resumed.current) return;
    resumed.current = true;
    const book = mostRecentUnfinished(library.books);
    if (book) openInReader(book.id, book.title);
  }, [library.loaded, library.books, openInReader]);

  // Library data is refreshed whenever its tab is opened.
  const selectTab = useCallback(
    (next: TabId) => {
      setTab(next);
      if (next === 'library') void library.reload();
    },
    [library],
  );

  const retry = useCallback(() => {
    void startup();
    void library.reload();
  }, [startup, library]);

  const banner = error ?? (library.error && !library.loaded ? library.error : null);

  const value = useMemo<AppContextValue>(
    () => ({
      settings,
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
      openSettings: () => setShowSettings(true),
      openVoices: () => setShowVoices(true),
    }),
    [settings, voiceList, voiceId, refreshVoices, refreshSettings, toast, openInReader, selectTab],
  );

  return (
    <AppContext.Provider value={value}>
      <div className="app-layout">
        <Navbar current={tab} onSelect={selectTab} onSettings={() => setShowSettings(true)} />

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
          <section hidden={tab !== 'library'} aria-label="Thư Viện & Ghi Chú"><LibraryPage library={library} /></section>
          <section hidden={tab !== 'stats'} aria-label="Thống Kê"><StatsPage active={tab === 'stats'} /></section>
        </main>

        <div className="toast" role="status" aria-live="polite">{toastText}</div>

        {showSettings && <SettingsDialog onClose={() => setShowSettings(false)} />}
        {showVoices && <VoicesDialog onClose={() => setShowVoices(false)} />}
      </div>
    </AppContext.Provider>
  );
}

export default App;
