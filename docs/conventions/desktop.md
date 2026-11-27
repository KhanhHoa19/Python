# Desktop App Conventions — `apps/desktop/`

> Applies to `apps/desktop/` (Python CustomTkinter GUI + Multi-threaded Audio Player).
> Read alongside `docs/conventions/common.md` and `docs/conventions/backend.md`.

## Architecture: Shared Backend Client
- The Desktop App and Web Frontend (`apps/web/`) **share the same backend (`backend/src/api/`) and MySQL database**.
- Communicate with the FastAPI REST API (`API_BASE_URL` from `.env`, default `http://127.0.0.1:5000`) via a dedicated API client module (`apps/desktop/api_client.py`) using `requests` or `httpx` with explicit timeouts.
- **Never** duplicate business logic (text chunking, SQL queries, TTS HTTP calls) inside Tkinter UI files.

## UI Structure (3 Main Screens, sidebar navigation)
Follow the layout defined in `De_cuong_Do_an_Python_v2.docx`:
1. **Tab Phòng Đọc (Main Reader):** Document selector, voice dropdown, scrollable text view with active sentence highlight (karaoke sync), click-to-jump sentence, playback controls (`Play/Pause`, `Previous/Next`, speed slider `0.75x–1.5x`), and "Save Audio Note" action.
2. **Tab Thư Viện & Ghi Chú (Library & Notes):** Cataloged books from MySQL, voice profile manager (including Instant Voice Cloning upload + consent checkbox), saved audio notes, and "Export Offline Audio" (`.wav`/`.mp3`).
3. **Tab Thống Kê (Analytics Dashboard):** Embedded Matplotlib bar/pie charts via `FigureCanvasTkAgg` + summary KPI table (words/min, average API latency in ms, API success rate).

## Threading & Audio Playback (Producer – Consumer)
- **Strict thread safety:** CustomTkinter / Tkinter is **not thread-safe**. Never modify widgets, labels, highlights, or progress bars from a background thread. Always schedule UI updates on the main thread via `widget.after(0, callback)`.
- **Producer – Consumer pattern (`threading` + `queue.Queue`):**
  - **Producer thread:** Pre-fetches audio for the next 2 sentences from the backend/TTS into a bounded `queue.Queue`.
  - **Consumer thread:** Dequeues audio files and plays them via `pygame.mixer` or `sounddevice`, then notifies the UI via `after()` and reports session telemetry to the backend.
- **Clean shutdown:** Stop worker threads (`threading.Event`), flush active reading session/bookmark, and call `pygame.mixer.quit()` when closing the window (`WM_DELETE_WINDOW`).

## Design system
- Mọi UI mới theo [design.md](design.md): dùng token trong `ui/theme.py` (`theme.ACCENT`, `**theme.SECONDARY`…), không mã màu thô; thêm màn mới bằng `SidebarTabs.add(...)` trong `ui/app.py`. Tk text tag và biểu đồ Matplotlib không nhận cặp sáng/tối: dùng `theme.mode_color(...)` và vẽ lại trong `refresh_theme()`.

## Matplotlib Integration
- Use `matplotlib.figure.Figure` + `FigureCanvasTkAgg` inside the Desktop GUI (do not call `plt.show()`, which spawns blocking external windows).
