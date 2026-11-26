# Audiobook TTS (monorepo)

| Thư mục | Nội dung |
|---------|----------|
| `backend/` | FastAPI API + core (gói `src`), tests, Dockerfile |
| `apps/web/` | Web React + Vite + TS (8 màn hình S01–S08; `npm test`, `npm run build`) |
| `apps/desktop/` | Desktop CustomTkinter (8 màn hình S01–S08, xem `apps/desktop/README.md`) |
| `packages/py-shared/` | Schema + API client dùng chung (chưa có code) |
| `storage/` | uploads, audio_cache, exports, voice_samples (không commit) |
| `db/` | schema.sql (sẽ xuất từ migration) |
| `docs/` | Đề cương, kế hoạch, `mockups/` (S01–S08), `conventions/`, `specs/` |

Chạy dev: `./start_dev.sh`  ·  Test backend: `cd backend && pytest -q`
Màn hình cần dựng: xem [docs/mockups/README.md](docs/mockups/README.md).
