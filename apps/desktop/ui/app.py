"""Main window: 3 tabs (Phòng Đọc, Thư Viện & Ghi Chú, Thống Kê), settings button, error banner, shortcuts."""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from typing import Any

import customtkinter as ctk

import config
from api_client import ApiClient
from player.audio_output import AudioOutput
from player.controller import ReaderController
from ui import theme
from ui.admin_tab import AdminTab
from ui.common import AppContext, error_text
from ui.dialogs import SettingsDialog
from ui.dispatcher import UiDispatcher
from ui.explore_tab import ExploreTab
from ui.images import CoverCache
from ui.library_tab import LibraryTab
from ui.quotes_tab import QuotesTab
from ui.reader_tab import ReaderTab
from ui.recommend_tab import RecommendTab
from ui.sidebar import SidebarTabs
from ui.stats_tab import StatsTab
from ui.viewmodels import most_recent_unfinished
from ui.voices_tab import VoicesTab

logger = logging.getLogger(__name__)

TAB_READER, TAB_EXPLORE, TAB_RECOMMEND, TAB_LIBRARY, TAB_QUOTES, TAB_STATS, TAB_VOICES, TAB_ADMIN = (
    "Phòng Đọc", "Khám Phá", "Gợi Ý", "Kệ Sách Của Tôi", "Trích Dẫn Yêu Thích", "Thống Kê", "Kho Giọng Đọc", "Quản Trị")


class _ListenerProxy:
    """The controller needs a listener before the reader tab exists; forward once it is set."""

    def __init__(self) -> None:
        self.target: Any = None

    def on_position(self, index: int) -> None:
        if self.target:
            self.target.on_position(index)

    def on_state(self, state: str) -> None:
        if self.target:
            self.target.on_state(state)

    def on_warning(self, message: str) -> None:
        if self.target:
            self.target.on_warning(message)

    def on_error(self, message: str) -> None:
        if self.target:
            self.target.on_error(message)


class App(ctk.CTk):
    def __init__(self, api: ApiClient, output: AudioOutput, user: dict[str, Any] | None = None):
        super().__init__()
        self.title("Audiobook TTS")
        self.geometry("1220x800")
        self.minsize(1000, 660)
        self.appearance = theme.load_appearance()
        ctk.set_appearance_mode(self.appearance)
        theme.apply()
        self.configure(fg_color=theme.BG)  # the root window was created before the theme was patched

        self.user: dict[str, Any] = user or {}
        self.logout_requested = False
        self.session_expired = False
        self.voices: list[dict[str, Any]] = []
        self.current_voice_id: str | None = None
        self.settings: dict[str, Any] = {}
        self._resumed = False
        self.categories: list[dict[str, Any]] = []
        self.category: str | None = None  # slug chosen in the sidebar; filters Khám phá and the shelf
        self._toast_job: str | None = None

        self.ui = UiDispatcher(self)
        proxy = _ListenerProxy()
        reader = ReaderController(api, output, proxy)
        self.ctx = AppContext(api=api, ui=self.ui, reader=reader, output=output, app=self, user=self.user, covers=CoverCache())
        api.on_unauthorized = lambda: self.ui.post(self._on_session_rejected)  # from any worker thread

        self.tabs = SidebarTabs(self, command=self._tab_changed)
        self.tabs.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.reader_tab = ReaderTab(self.tabs.add(TAB_READER, "🎧"), self.ctx)
        self.explore_tab = ExploreTab(self.tabs.add(TAB_EXPLORE, "🧭"), self.ctx)
        self.recommend_tab = RecommendTab(self.tabs.add(TAB_RECOMMEND, "✨"), self.ctx)
        self.library_tab = LibraryTab(self.tabs.add(TAB_LIBRARY, "📚"), self.ctx)
        self.quotes_tab = QuotesTab(self.tabs.add(TAB_QUOTES, "⭐"), self.ctx)
        self.stats_tab = StatsTab(self.tabs.add(TAB_STATS, "📊"), self.ctx)
        self.voices_tab = VoicesTab(self.tabs.add(TAB_VOICES, "🎙"), self.ctx)
        screens = [self.reader_tab, self.explore_tab, self.recommend_tab, self.library_tab, self.quotes_tab, self.stats_tab, self.voices_tab]
        self.admin_tab: AdminTab | None = None
        if self.user.get("role") == "admin":  # the screen does not exist for anyone else
            self.admin_tab = AdminTab(self.tabs.add(TAB_ADMIN, "🛡"), self.ctx)
            screens.append(self.admin_tab)
        for tab in screens:
            tab.pack(fill="both", expand=True, padx=24, pady=(18, 8))
        proxy.target = self.reader_tab

        self._build_banner()
        self.tabs.set_account(self.user)
        self.tabs.add_tool("⚙   Kết nối & Cài đặt", self.open_settings)
        self.theme_btn = self.tabs.add_tool("", self.toggle_appearance)
        self.tabs.add_tool("⎋   Đăng xuất", self.logout)
        self._show_appearance()

        self.toast_label = ctk.CTkLabel(self.tabs.content, text="", anchor="w", text_color=theme.TEXT_2)
        self.toast_label.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 8))

        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.ui.start()
        self.startup_load()

    # -- layout --------------------------------------------------------------------------------------------

    def _build_banner(self) -> None:
        self.banner = ctk.CTkFrame(self.tabs.content, fg_color=theme.DANGER, corner_radius=10)
        self.banner_label = ctk.CTkLabel(self.banner, text="", text_color="#ffffff", anchor="w", wraplength=760)
        self.banner_label.pack(side="left", padx=12, pady=8)
        ctk.CTkButton(self.banner, text="Thử lại", width=80, fg_color="#ffffff", text_color="#9e2d22",
                      hover_color="#f3e3e0", command=self._retry).pack(side="right", padx=10)

    # -- account ---------------------------------------------------------------------------------------------

    def logout(self) -> None:
        """Close the window and let main() show the sign-in form again."""
        self.logout_requested = True
        self._on_close()

    def _on_session_rejected(self) -> None:
        """The backend refused our token (expired, or the account is gone)."""
        if not self.logout_requested:
            self.session_expired = True
            self.logout()

    # -- appearance ------------------------------------------------------------------------------------------

    def _show_appearance(self) -> None:
        icon = {"System": "🖥", "Light": "☀", "Dark": "🌙"}[self.appearance]
        self.theme_btn.configure(text=f"{icon}   Giao diện: {theme.APPEARANCE_LABEL[self.appearance]}")

    def toggle_appearance(self) -> None:
        """Cycle Tự động → Sáng → Tối. Widgets switch by themselves; Tk text tags and charts are redrawn."""
        order = theme.APPEARANCES
        self.appearance = order[(order.index(self.appearance) + 1) % len(order)]
        ctk.set_appearance_mode(self.appearance)
        theme.save_appearance(self.appearance)
        self._show_appearance()
        self.after(50, self.reader_tab.refresh_theme)
        if self.tabs.get() == TAB_STATS:
            self.after(50, self.stats_tab.refresh)

    # -- shared state / navigation ---------------------------------------------------------------------------

    def startup_load(self) -> None:
        """Load settings and voices, then the library (which also resumes the last book)."""

        def work() -> tuple[dict[str, Any], dict[str, Any]]:
            return self.ctx.api.get_settings(), self.ctx.api.list_voices()

        self.ui.run_in_thread(work, self._startup_loaded, lambda exc: self.show_error(error_text(exc)))
        self.ui.run_in_thread(self.ctx.api.list_categories, self._categories_loaded, lambda _exc: None)
        self.library_tab.refresh()

    def _categories_loaded(self, categories: list[dict[str, Any]]) -> None:
        self.categories = categories
        self._show_category_chips()

    def _show_category_chips(self) -> None:
        for tab in (self.explore_tab, self.library_tab):
            tab.chips.set_categories(self.categories, self.category)

    def pick_category(self, slug: str | None) -> None:
        """A topic tag on Khám phá or Kệ sách (click again to clear); both screens share the choice."""
        self.category = None if slug == self.category else slug
        self._show_category_chips()
        if self.tabs.get() in (TAB_EXPLORE, TAB_LIBRARY):
            self._tab_changed()

    def _startup_loaded(self, result: tuple[dict[str, Any], dict[str, Any]]) -> None:
        settings, voices = result
        self.hide_error()
        self.settings = settings
        self.current_voice_id = settings["default_voice"]
        self.set_voices(voices)
        self.apply_settings(settings)

    def set_voices(self, data: dict[str, Any]) -> None:
        self.voices = data["voices"]
        ids = {v["voice_id"] for v in self.voices}
        if self.current_voice_id not in ids:
            self.current_voice_id = self.voices[0]["voice_id"] if self.voices else None
        self.ctx.reader.voice = self.current_voice_id
        self.reader_tab.set_voices(self.voices, self.current_voice_id)

    def select_voice(self, voice_id: str) -> None:
        self.current_voice_id = voice_id
        self.reader_tab.set_voices(self.voices, voice_id)
        self.ctx.reader.set_voice(voice_id)

    def apply_settings(self, settings: dict[str, Any]) -> None:
        self.settings = settings
        self.ctx.reader.prefetch = int(settings["prefetch_count"])
        self.ctx.reader.chapter_chime = bool(settings.get("chapter_chime", True))
        self.ctx.reader.character_voice = settings.get("character_voice") or None
        self.ctx.reader.ambient.configure(int(settings.get("ambient_track") or 0), float(settings.get("ambient_volume", 0.4)))
        self.reader_tab.refresh_ambient()
        if not self.ctx.reader.is_playing:
            self.ctx.reader.speed = float(settings["default_speed"])
            self.reader_tab.set_speed_label(self.ctx.reader.speed)

    def open_voices(self) -> None:
        self.tabs.set(TAB_VOICES, notify=True)

    def reload_shared(self) -> None:
        """Voices and categories changed (an admin published a voice, edited a category): refresh what every screen shows."""
        self.ui.run_in_thread(self.ctx.api.list_voices, self.set_voices, lambda _exc: None)
        self.ui.run_in_thread(self.ctx.api.list_categories, self._categories_loaded, lambda _exc: None)

    def open_settings(self) -> None:
        SettingsDialog(self, self.ctx)

    def open_in_reader(self, book_id: int, title: str, sentence_index: int | None = None) -> None:
        self.toast(f'Đang mở "{title}"…')

        def work() -> int:
            start = self.ctx.reader.load_book(book_id, title)
            return start if sentence_index is None else min(sentence_index, max(self.ctx.reader.total - 1, 0))

        def done(start: int) -> None:
            self.ctx.reader.index = start
            saved = self.ctx.reader.saved_voice
            if saved and saved != self.current_voice_id and any(v["voice_id"] == saved for v in self.voices):
                self.select_voice(saved)  # the voice last used for this book
            self.reader_tab.show_book(start)
            self.tabs.set(TAB_READER)
            self.toast("")

        self.ui.run_in_thread(work, done, lambda exc: self.show_error(error_text(exc)))

    def on_book_renamed(self, book_id: int, title: str) -> None:
        """Keep the title shown in the reader in step with a rename done in the library."""
        book = self.ctx.reader.book
        if book and book.book_id == book_id:
            book.title = title
            self.reader_tab.title_label.configure(text=title)

    def close_reader_book(self) -> None:
        self.ctx.reader.close_book()
        self.reader_tab.title_label.configure(text="Chưa chọn tài liệu")
        self.reader_tab.empty_hint.grid()
        self.reader_tab.toc_btn.grid_remove()
        self.reader_tab.text.configure(state="normal")
        self.reader_tab.text.delete("1.0", "end")
        self.reader_tab.text.configure(state="disabled")

    @property
    def resumed(self) -> bool:
        """True once the book being read last time was reopened (or a book is already open)."""
        return self._resumed or bool(self.ctx.reader.book)

    def on_library_loaded(self, books: list[dict[str, Any]]) -> None:
        """First load only: reopen the book that was being read, positioned but not playing."""
        if self._resumed or self.ctx.reader.book:
            return
        self._resumed = True
        book = most_recent_unfinished(books)
        if book:
            self.open_in_reader(book["id"], book["title"])

    # -- messages --------------------------------------------------------------------------------------------------

    def show_error(self, message: str) -> None:
        self.banner_label.configure(text=message)
        self.banner.grid(row=0, column=0, sticky="ew", padx=28, pady=(14, 0))

    def hide_error(self) -> None:
        self.banner.grid_remove()

    def _retry(self) -> None:
        self.hide_error()
        self.startup_load()

    def toast(self, message: str) -> None:
        self.toast_label.configure(text=message)
        if self._toast_job:
            self.after_cancel(self._toast_job)
        if message:
            self._toast_job = self.after(5000, lambda: self.toast_label.configure(text=""))

    # -- tabs & keyboard ----------------------------------------------------------------------------------------------

    def _tab_changed(self) -> None:
        current = self.tabs.get()
        if current == TAB_EXPLORE:
            self.explore_tab.refresh()
        elif current == TAB_RECOMMEND:
            self.recommend_tab.refresh()
        elif current == TAB_LIBRARY:
            self.library_tab.refresh()
        elif current == TAB_QUOTES:
            self.quotes_tab.refresh()
        elif current == TAB_STATS:
            self.stats_tab.refresh()
        elif current == TAB_VOICES:
            self.voices_tab.refresh()
        elif current == TAB_ADMIN and self.admin_tab:
            self.admin_tab.refresh()

    def show_quotes_for(self, book_id: int | None) -> None:
        """Open Trích dẫn yêu thích, limited to one book (or all of them with None)."""
        self.quotes_tab.show_book(book_id)
        if self.tabs.get() == TAB_QUOTES:
            self.quotes_tab.refresh()
        else:
            self.tabs.set(TAB_QUOTES, notify=True)

    def _typing_in_field(self) -> bool:
        widget = self.focus_get()
        if isinstance(widget, tk.Entry):
            return True
        return isinstance(widget, tk.Text) and str(widget.cget("state")) == "normal"

    def _bind_shortcuts(self) -> None:
        reader = self.ctx.reader

        def on_reader(action: Any) -> Any:
            def handler(_event: tk.Event) -> str | None:
                if self.tabs.get() != TAB_READER or self._typing_in_field():
                    return None
                action()
                return "break"

            return handler

        def change_speed(step: int) -> None:
            levels = list(config.SPEED_LEVELS)
            current = min(range(len(levels)), key=lambda i: abs(levels[i] - reader.speed))
            new = levels[min(max(current + step, 0), len(levels) - 1)]
            self.reader_tab.set_speed_label(new)
            reader.set_speed(new)

        self.bind("<space>", on_reader(reader.toggle))
        self.bind("<Left>", on_reader(reader.previous))
        self.bind("<Right>", on_reader(reader.next))
        self.bind("<Up>", on_reader(lambda: change_speed(1)))
        self.bind("<Down>", on_reader(lambda: change_speed(-1)))
        self.bind("<n>", on_reader(self.reader_tab._note))
        self.bind("<b>", on_reader(self.reader_tab._bookmark))

    # -- shutdown ----------------------------------------------------------------------------------------------------------

    def _on_close(self) -> None:
        """Stop workers, flush bookmark + session (bounded wait), release audio, then close."""
        self.ctx.api.on_unauthorized = None  # the final saves below may be refused; that is not news any more
        self.quotes_tab.shutdown()
        self.ui.close()
        flusher = threading.Thread(target=self.ctx.reader.close_book, daemon=True)
        flusher.start()
        flusher.join(timeout=4.0)
        try:
            self.ctx.output.close()
            if not self.logout_requested:  # after "Đăng xuất" the sign-in window reuses this client (quick-login boxes)
                self.ctx.api.close()
        finally:
            self.destroy()
