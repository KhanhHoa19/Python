# Common Engineering Conventions

> Judgment-based conventions for team members and AI coding assistants.
> Hard rules (lint, typecheck, tests) are enforced by tooling — do not restate or fight them:
> - Python lint & formatting: `ruff check .` (config in `pyproject.toml`)
> - Python type checking: `mypy src`
> - Python test suite: `pytest tests/ -v`
> - Frontend build & typecheck: `cd apps/web && npm run build`

## SpecKit & Planning Workflow
- Respect the SpecKit workflow enforced in `AGENTS.md`: do **not** implement major new features without a corresponding spec/plan/task in `specs/` or `.specify/`.
- Check `.specify/memory/constitution.md` before architectural changes.

## Git & Team Collaboration
- **Protected `main` branch:** Never commit or push directly to `main`.
- **Branch naming:** `feature/<short-kebab>` or `fix/<short-kebab>` (e.g., `feature/desktop-customtkinter`, `fix/mysql-ssl-config`).
- **Conventional Commits:** `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:` with imperative subject (e.g., `feat: add voice cloning endpoint`).
- **One logical concern per commit:** Never use `git add -A`; stage specific files only.
- **No AI-authorship trailers:** Commit as the human author only. Do not append `Co-Authored-By:` or `Generated with ...` markers.

## Shared Database & Secrets
- **Zero secrets in Git:** Never commit `.env`, API keys (`OPENAI_API_KEY`, ElevenLabs/FPT.AI keys), or MySQL passwords. Update `.env.example` whenever adding new environment variables.
- **Shared team DB:** Teammates share a single MySQL instance via `.env` (`DB_USE_SQLITE=false`, `DB_HOST=<shared-ip>`). Use `DB_USE_SQLITE=true` only for isolated local fallback/testing.

## Correctness & Design
- **No placeholder logic on main paths:** Never commit `# TODO: implement`, `pass` stubs, or `raise NotImplementedError` in production code paths.
- **No duplicated logic:** Search existing modules (`backend/src/core/`, `apps/web/src/hooks/`) before writing new utilities.
- **Encapsulation:** Functions and components must validate/handle their own edge cases (empty inputs, `None`, network timeouts) rather than relying on comments.

## Testing & Quality Gate
- **Offline tests only:** Never call live paid TTS APIs or external services in automated tests. Mock external HTTP/TTS boundaries using `unittest.mock` or `pytest-mock`.
- **Verify before reporting done:** Run `ruff check .`, `mypy src`, and `pytest tests/ -q` after backend/core edits; run `npm run build` after frontend edits.
