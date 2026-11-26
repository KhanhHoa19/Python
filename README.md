# Audiobook TTS (monorepo)

| Thư mục | Nội dung |
|---------|----------|
| `backend/` | Flask API + core (gói `src`), tests, Dockerfile |
| `apps/web/` | Web React + Vite + TS |
| `apps/desktop/` | Desktop CustomTkinter (chưa có code) |
| `packages/py-shared/` | Schema + API client dùng chung (chưa có code) |
| `storage/` | uploads, audio_cache, exports, voice_samples (không commit) |
| `db/` | schema.sql (sẽ xuất từ migration) |
| `docs/` | Đề cương, kế hoạch, `mockups/` (S01–S08), `conventions/`, `specs/` |

Chạy dev: `./start_dev.sh`  ·  Test backend: `cd backend && pytest -q`
Màn hình cần dựng: xem [docs/mockups/README.md](docs/mockups/README.md).
