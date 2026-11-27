# Smart Audiobook Reader — AI Coding Conventions

Follow these conventions on **every** change — they are the source of truth for this repo.
Common rules are imported below (Claude Code loads `@`-imported files automatically):

@docs/conventions/common.md

## Giao diện (bắt buộc cho mọi màn hình mới)

Mọi màn hình và chức năng có giao diện **phải bám design system** trong [docs/conventions/design.md](docs/conventions/design.md) (màu, chữ, khung sidebar, thành phần dùng chung, web và desktop giống nhau). Không dùng mã màu thô; dùng token.

## Per-domain style guides

When working inside a specific layer or app, follow its dedicated convention guide:

- **Backend (`backend/src/api`, `backend/src/core`, `backend/src/cli` — Python 3.11+, FastAPI, SQLAlchemy/MySQL, TTS, Matplotlib/Pandas):** [docs/conventions/backend.md](docs/conventions/backend.md)
- **Web Frontend (`apps/web/` — React 18, TypeScript, Vite):** [docs/conventions/frontend.md](docs/conventions/frontend.md)
- **Desktop App (`apps/desktop/` — Python CustomTkinter GUI + Producer/Consumer Audio):** [docs/conventions/desktop.md](docs/conventions/desktop.md)
