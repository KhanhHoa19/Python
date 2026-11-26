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
from ui.common import AppContext, error_text
from ui.dialogs import SettingsDialog, VoicesDialog
from ui.dispatcher import UiDispatcher
from ui.library_tab import LibraryTab
from ui.reader_tab import ReaderTab
from ui.stats_tab import StatsTab
from ui.viewmodels import most_recent_unfinished

logger = logging.getLogger(__name__)

TAB_READER, TAB_LIBRARY, TAB_STATS = "Phòng Đọc", "Thư Viện & Ghi Chú", "Thống Kê"


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
    def __init__(self, api: ApiClient, output: AudioOutput):
        super().__init__()
        self.title("Audiobook TTS")
        self.geometry("1040x780")
        self.minsize(860, 640)
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.voices: list[dict[str, Any]] = []
        self.current_voice_id: str | None = None
        self.settings: dict[str, Any] = {}
        self._resumed = False
        self._toast_job: str | None = None

        self.ui = UiDispatcher(self)
        proxy = _ListenerProxy()
        reader = ReaderController(api, output, proxy)
        self.ctx = AppContext(api=api, ui=self.ui, reader=reader, output=output, app=self)

        self._build_header()
        self.tabs = ctk.CTkTabview(self, command=self._tab_changed)
        self.tabs.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 4))
        self.reader_tab = ReaderTab(self.tabs.add(TAB_READER), self.ctx)
        self.library_tab = LibraryTab(self.tabs.add(TAB_LIBRARY), self.ctx)
        self.stats_tab = StatsTab(self.tabs.add(TAB_STATS), self.ctx)
        for tab in (self.reader_tab, self.library_tab, self.stats_tab):
            tab.pack(fill="both", expand=True)
        proxy.target = self.reader_tab

        self.toast_label = ctk.CTkLabel(self, text="", anchor="w", text_color=("gray25", "gray75"))
        self.toast_label.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 6))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.ui.start()
        self.startup_load()

    # -- layout --------------------------------------------------------------------------------------------

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 0))
        header.columnconfigure(1, weight=1)
        ctk.CTkLabel(header, text="🎧 Audiobook TTS", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0)
        ctk.CTkButton(header, text="⚙", width=40, command=self.open_settings).grid(row=0, column=2)

        self.banner = ctk.CTkFrame(self, fg_color="#d64545", corner_radius=6)
        self.banner_label = ctk.CTkLabel(self.banner, text="", text_color="white", anchor="w", wraplength=800)
        self.banner_label.pack(side="left", padx=10, pady=6)
        ctk.CTkButton(self.banner, text="Thử lại", width=80, fg_color="white", text_color="#d64545",
                      hover_color="#f0f0f0", command=self._retry).pack(side="right", padx=8)
        self.rowconfigure(1, weight=0)

    # -- shared state / navigation ---------------------------------------------------------------------------

    def startup_load(self) -> None:
        """Load settings and voices, then the library (which also resumes the last book)."""

        def work() -> tuple[dict[str, Any], dict[str, Any]]:
            return self.ctx.api.get_settings(), self.ctx.api.list_voices()

        self.ui.run_in_thread(work, self._startup_loaded, lambda exc: self.show_error(error_text(exc)))
        self.library_tab.refresh()

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
        if not self.ctx.reader.is_playing:
            self.ctx.reader.speed = float(settings["default_speed"])
            self.reader_tab.set_speed_label(self.ctx.reader.speed)

    def open_voices(self) -> None:
        VoicesDialog(self, self.ctx, on_select=self.select_voice)

    def open_settings(self) -> None:
        SettingsDialog(self, self.ctx)

    def open_in_reader(self, book_id: int, title: str, sentence_index: int | None = None) -> None:
        self.toast(f'Đang mở "{title}"…')

        def work() -> int:
            start = self.ctx.reader.load_book(book_id, title)
            return start if sentence_index is None else min(sentence_index, max(self.ctx.reader.total - 1, 0))

        def done(start: int) -> None:
            self.ctx.reader.index = start
            self.reader_tab.show_book(start)
            self.tabs.set(TAB_READER)
            self.toast("")

        self.ui.run_in_thread(work, done, lambda exc: self.show_error(error_text(exc)))

    def close_reader_book(self) -> None:
        self.ctx.reader.close_book()
        self.reader_tab.title_label.configure(text="Chưa chọn tài liệu")
        self.reader_tab.empty_hint.grid()
        self.reader_tab.text.configure(state="normal")
        self.reader_tab.text.delete("1.0", "end")
        self.reader_tab.text.configure(state="disabled")

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
        self.banner.grid(row=1, column=0, sticky="ew", padx=12, pady=(6, 0))

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
        if current == TAB_LIBRARY:
            self.library_tab.refresh()
        elif current == TAB_STATS:
            self.stats_tab.refresh()

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

    # -- shutdown ----------------------------------------------------------------------------------------------------------

    def _on_close(self) -> None:
        """Stop workers, flush bookmark + session (bounded wait), release audio, then close."""
        self.ui.close()
        flusher = threading.Thread(target=self.ctx.reader.close_book, daemon=True)
        flusher.start()
        flusher.join(timeout=4.0)
        try:
            self.ctx.output.close()
            self.ctx.api.close()
        finally:
            self.destroy()
