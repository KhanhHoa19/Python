# Backend Conventions — `backend/src/api` & `backend/src/core`

> Applies to `backend/src/api/` (FastAPI REST API + Pydantic), `backend/src/core/` (business logic), and `backend/src/cli/`.
> Read alongside `docs/conventions/common.md`.
> **Canonical references:** Copy patterns from `backend/src/api/routes/books.py`, `backend/src/api/schemas/book_schemas.py`, and `backend/src/core/ingestion/service.py`.

## Runtime & Tooling
- **Python 3.11+** with modern type annotations (`dict[str, Any]`, `list[int]`, `str | None`).
- **Source of truth for config:** All environment variables are loaded via `Settings` in `backend/src/core/config.py` (`get_settings()`). Never call `os.getenv()` directly inside routes or services.
- **Active codebase:** Put all new shared backend logic in `backend/src/core/` and HTTP endpoints in `backend/src/api/`. Legacy top-level folders (`backend/src/ingestion/`, `backend/src/player/`, `backend/src/storage/`, `backend/src/tts/`, `backend/src/telemetry/`, `backend/src/models/`) belong to the v1 CLI and must not receive new web/desktop features.

## Layered Architecture (Strict Boundaries)
```text
src/api/routes/*.py        # HTTP parsing, Pydantic validation, status codes only
  └─> src/core/*/          # Business logic (ingestion, tts, player, telemetry, analytics)
        └─> src/core/storage/repositories.py   # ALL SQLAlchemy / SQL queries live here
```
- **Never write SQL or SQLAlchemy queries inside `backend/src/api/routes/`** or UI code. All DB access goes through `repositories.py` using `get_db_connection()` from `backend/src/core/storage/db.py`.
- **Parameterized queries only:** Never format user input into raw SQL strings (`f"SELECT ... {x}"`).
- **Connection pooling:** Always use the singleton pooled engine from `get_db_engine()` (`QueuePool` for MySQL, `StaticPool` for SQLite).

## Database & Migrations
- Schema and migrations live in `backend/src/core/storage/migrations.py`.
- Adding a column to an existing table: append it to `COLUMN_UPGRADES` (idempotent `ALTER TABLE`). Changing a constraint needs its own upgrade function plus a test on an old-schema database (see `tests/integration/test_account_migration.py`). **Back up MySQL before the first start with a new schema** (`docker exec studylab-mysql mysqldump ...`).
- Both Web (`apps/web/`) and Desktop (`apps/desktop/`) share the same MySQL database through `backend/src/api/`.
- When adding new tables from the project outline (e.g., `voice_profiles` for Voice Cloning, `audio_notes` for study bookmarks), add idempotent `CREATE TABLE IF NOT EXISTS` statements in `migrations.py` and keep SQLite fallback compatibility.

## Accounts & Access Control (every new endpoint)
- **Every route except the short PUBLIC list in `tests/integration/test_route_audit.py` needs a signed-in user** (health, login/register, demo accounts in dev mode, cover images and ambient sound files, which `<img>`/`<audio>` fetch without a token). That test is generated from the OpenAPI document: a new route that forgets `current_user` fails it, and so does an `/api/admin/*` route that lets a member in. Adding a deliberately public route means adding it to that list in the same change. Routers are included with `dependencies=[Depends(current_user)]` in `api/app.py`; a route that needs the user takes `user: User = Depends(current_user)` (`api/deps.py`). Admin-only routes use `require_admin`.
- **Never fetch user data by id alone.** Books go through `visible_book(engine, id, user)` / `editable_book(...)`, cloned voices through `check_voice_access(...)`, and per-user repositories (`SqlBookmarkRepository`, `SqlSessionRepository`, `SqlNoteRepository`, `SqlUserSettingsRepository`) are constructed with `user.id`. Someone else's data must answer **404**, exactly like a missing row (403 only when the thing is visible but not editable).
- **A new table with personal data gets a `user_id`/`owner_id` column, and a test in `tests/integration/test_accounts.py` showing that user B cannot read, change or delete user A's rows** (and that an admin cannot either unless the feature says so).
- **Shared cost, shared limits:** the daily character limit is system-wide and only an admin sets it; one HeyGen account serves everyone (see `MAX_VOICES_PER_USER`).
- **Secrets:** `JWT_SECRET`, `ADMIN_PASSWORD` and the `DEMO_PASSWORD_*` of the dev quick-login accounts come from the environment (`.env`, never the repository); never log tokens or passwords. Passwords are hashed with scrypt (`core/auth/security.py`).
- **Tests sign in** through `tests/auth_helpers.py` (`use_engine`, `sign_in`, `tester`); do not bypass the dependency.

## Validation & API Contracts
- **Pydantic schemas (`backend/src/api/schemas/`):** Every request body and response shape must be defined as a Pydantic `BaseModel`. This is the **source of truth** consumed by both Web (`apps/web/`) and Desktop (`apps/desktop/`).
- **Consistent error responses:** Return structured JSON errors (`{"error": "message"}`) with appropriate HTTP status codes (`400`, `404`, `422`, `500`). Never leak stack traces or secrets in API responses.

## TTS Providers, Network Probe & Analytics
- **TTS Adapters (`backend/src/core/tts/`):** Implement `TTSProvider` in `backend/src/core/tts/base.py` and register in `factory.py`. Strictly use third-party APIs (`edge-tts`, `openai`, `elevenlabs`, etc.) — never add local neural network training pipelines.
- **Network Probing (`backend/src/core/telemetry/`):** Use `socket` / ping probes with explicit short timeouts; never block playback threads on telemetry failures.
- **Analytics (`backend/src/core/analytics/`):** Use `pandas` / `numpy` for metric aggregation and **must** set `matplotlib.use("Agg")` (headless) when generating chart images in backend/API routes.

## External Integrations (`backend/src/integrations/`)
- Any webhook/n8n/automation code must live in `backend/src/integrations/`, run asynchronously/non-blocking (timeout <= 3s), and degrade gracefully if unreachable.
