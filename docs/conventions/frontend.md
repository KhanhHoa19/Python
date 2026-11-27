# Web Frontend Conventions — `apps/web/`

> Applies to `apps/web/` (React 18, TypeScript, Vite, Lucide icons).
> Read alongside `docs/conventions/common.md`.
> **Canonical references:** Copy patterns from `apps/web/src/api/booksApi.ts`, `apps/web/src/hooks/useAudioPlayer.ts`, and `apps/web/src/pages/PlayerPage.tsx`.

## Directory Structure
- `apps/web/src/pages/`: Top-level screens (`ReaderPage.tsx` S03, `LibraryPage.tsx` S01+S06, `StatsPage.tsx` S08).
- `apps/web/src/components/`: Reusable UI grouped by feature (`Reader/`, `Library/`, `Stats/`, `Dialogs/` for S02/S05/S06/S07 and the clone-voice dialog, `Admin/` for the S11 panels, `Sidebar/`, `common/`).
- `apps/web/src/hooks/`: Stateful logic and side effects (`useAudioPlayer.ts`, `useLibrary.ts`, `useReaderShortcuts.ts`, `useTextSelection.ts`, `useAsyncData.ts`, `useBlobAudio.ts`).
- `apps/web/src/lib/`: Pure functions with unit tests (`audioPrefetcher.ts`, `format.ts`, `books.ts`, `voices.ts`). No React, no DOM.
- `apps/web/src/context/`: `AppContext` (settings, voices, navigation, toast/error banner).
- `apps/web/src/api/`: HTTP client (`client.ts`) and domain wrappers (`booksApi`, `playerApi`, `voicesApi`, `notesApi`, `settingsApi`, `healthApi`, `exportApi`, `analyticsApi`).
- `apps/web/src/types/`: TypeScript interfaces matching backend Pydantic schemas.

## Data Fetching & API Contracts
- **One HTTP client:** Every API call must go through `apps/web/src/api/client.ts` and domain modules in `apps/web/src/api/`. **Never** call `fetch()` or `axios` directly inside components or pages.
- **Backend is the source of truth:** Keep `apps/web/src/types/*.ts` aligned with `backend/src/api/schemas/*.py`. Do not invent client-only field names that diverge from the API contract.

## Components, Hooks & State
- **Functional components only** with explicit TypeScript prop interfaces (`interface FooProps { ... }`).
- **Separate UI from logic:** Audio playback, buffering, sentence karaoke highlighting, and keyboard shortcuts belong in `apps/web/src/hooks/` — keep `.tsx` components focused on rendering and user events.
- **Cleanup side effects:** Always clean up `Audio` elements, timers, and `window` event listeners inside `useEffect` return callbacks to prevent memory leaks or overlapping audio playback.
- **No heavy client-side filtering/aggregation:** Let backend endpoints compute analytics, sentence counts, and search/filter results.

## Design system
- Mọi UI mới theo [design.md](design.md): chỉ dùng token trong `index.css` (`var(--accent)`…), không mã màu thô; thêm màn mới vào `Sidebar.tsx`; mở đầu bằng `PageHeader`.

## Verification
- Before finishing any frontend change, run `cd apps/web && npm run build` (`tsc && vite build`) and `npm test` (Vitest, pure logic in `src/lib/`), with zero errors.
- Mount `useAudioPlayer` with `key={bookId}`: its cleanup reports progress for the book it was created with.
- Screen text is Vietnamese and must match `docs/mockups/` exactly so web and desktop stay identical.
