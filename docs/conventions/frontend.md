# Web Frontend Conventions — `apps/web/`

> Applies to `apps/web/` (React 18, TypeScript, Vite, Lucide icons).
> Read alongside `docs/conventions/common.md`.
> **Canonical references:** Copy patterns from `apps/web/src/api/booksApi.ts`, `apps/web/src/hooks/useAudioPlayer.ts`, and `apps/web/src/pages/PlayerPage.tsx`.

## Directory Structure
- `backend/src/pages/`: Top-level route views (`LibraryPage.tsx`, `PlayerPage.tsx`, `DashboardPage.tsx`).
- `backend/src/components/`: Reusable UI grouped by feature (`BookUploader/`, `Library/`, `Player/`, `Dashboard/`, `Navbar/`).
- `backend/src/hooks/`: Stateful logic and side effects (`useAudioPlayer.ts`, `useBookCatalog.ts`, `useDashboard.ts`).
- `backend/src/api/`: HTTP client (`client.ts`) and domain API wrappers (`booksApi.ts`, `playerApi.ts`, `analyticsApi.ts`).
- `backend/src/types/`: TypeScript interfaces matching backend Pydantic schemas (`book.ts`, `player.ts`, `analytics.ts`).

## Data Fetching & API Contracts
- **One HTTP client:** Every API call must go through `apps/web/src/api/client.ts` and domain modules in `apps/web/src/api/`. **Never** call `fetch()` or `axios` directly inside components or pages.
- **Backend is the source of truth:** Keep `backend/src/types/*.ts` aligned with `backend/src/api/schemas/*.py`. Do not invent client-only field names that diverge from the API contract.

## Components, Hooks & State
- **Functional components only** with explicit TypeScript prop interfaces (`interface FooProps { ... }`).
- **Separate UI from logic:** Audio playback, buffering, sentence karaoke highlighting, and keyboard shortcuts belong in `backend/src/hooks/` — keep `.tsx` components focused on rendering and user events.
- **Cleanup side effects:** Always clean up `Audio` elements, timers, and `window` event listeners inside `useEffect` return callbacks to prevent memory leaks or overlapping audio playback.
- **No heavy client-side filtering/aggregation:** Let backend endpoints compute analytics, sentence counts, and search/filter results.

## Verification
- Before finishing any frontend change, run `cd apps/web && npm run build` (`tsc && vite build`) and ensure zero TypeScript or Vite build errors.
