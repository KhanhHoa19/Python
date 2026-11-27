"""S06 – Trích dẫn yêu thích: saved passages, filtered by book or feeling, with a play-all mode."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

from player.quote_playlist import QuotePlaylist
from ui import theme
from ui.common import AppContext, error_text
from ui.dialogs import EditNoteDialog
from ui.viewmodels import EMOTIONS, emotion_label, format_datetime, matches_quote

_ALL_FEELINGS = "Tất cả cảm xúc"
_ALL_BOOKS = "Tất cả sách"


class QuotesTab(ctk.CTkFrame):
    def __init__(self, master: tk.Misc, ctx: AppContext):
        super().__init__(master, fg_color="transparent")
        self.ctx = ctx
        self.notes: list[dict[str, Any]] = []
        self.books: dict[str, int] = {}
        self.book_id: int | None = None  # set from a book card ("Trích dẫn" button)
        self.shown: list[dict[str, Any]] = []
        self._cards: dict[int, ctk.CTkFrame] = {}
        self._playing_id: int | None = None
        self.playlist = QuotePlaylist(
            fetch=lambda note_id: ctx.api.note_audio(note_id), output=ctx.output,
            on_change=lambda pos: ctx.ui.post(self._playlist_changed, pos),
            on_error=lambda message: ctx.ui.post(ctx.app.toast, message))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(titles, text="Trích dẫn yêu thích", anchor="w", font=theme.font(26, "bold")).pack(anchor="w")
        ctk.CTkLabel(titles, text="Những đoạn hay bạn đã đánh dấu khi nghe, kèm âm thanh lưu sẵn.", anchor="w",
                     text_color=theme.MUTED).pack(anchor="w")
        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.grid(row=0, column=1, sticky="e")
        self.progress_label = ctk.CTkLabel(controls, text="", text_color=theme.MUTED)
        self.prev_btn = ctk.CTkButton(controls, text="⏮", width=40, command=lambda: self.playlist.step(-1), **theme.GHOST)
        self.next_btn = ctk.CTkButton(controls, text="⏭", width=40, command=lambda: self.playlist.step(1), **theme.GHOST)
        self.play_btn = ctk.CTkButton(controls, text="▶ Phát liên tục", command=self._toggle_playlist)
        self.play_btn.pack(side="right")

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=1, column=0, sticky="ew", pady=4)
        toolbar.columnconfigure(0, weight=1)
        self.search = ctk.CTkEntry(toolbar, placeholder_text="🔍 Tìm trong trích dẫn…")
        self.search.grid(row=0, column=0, sticky="ew")
        self.search.bind("<KeyRelease>", lambda _e: self._render())
        self.book_box = ctk.CTkComboBox(toolbar, values=[_ALL_BOOKS], width=240, state="readonly", command=self._book_chosen)
        self.book_box.set(_ALL_BOOKS)
        self.book_box.grid(row=0, column=1, padx=(6, 0))

        self.feeling = ctk.CTkSegmentedButton(self, values=[_ALL_FEELINGS] + [label for _, label in EMOTIONS],
                                              command=lambda _v: self.refresh())
        self.feeling.set(_ALL_FEELINGS)
        self.feeling.grid(row=2, column=0, sticky="w", pady=(6, 6))

        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list.grid(row=3, column=0, sticky="nsew", pady=(4, 8))
        self.list.columnconfigure(0, weight=1)

    # -- data ---------------------------------------------------------------------------------------------

    def show_book(self, book_id: int | None) -> None:
        """Limit the list to one book (from a book card) or show everything."""
        self.book_id = book_id

    def _tag(self) -> str | None:
        return next((value for value, label in EMOTIONS if label == self.feeling.get()), None)

    def refresh(self) -> None:
        self._message("Đang tải…")
        book_id, tag = self.book_id, self._tag()

        def work() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            return self.ctx.api.list_notes(book_id, tag), self.ctx.api.list_books()

        self.ctx.ui.run_in_thread(work, self._loaded, lambda exc: self._message(error_text(exc), error=True))

    def _loaded(self, result: tuple[list[dict[str, Any]], list[dict[str, Any]]]) -> None:
        self.notes, books = result
        self.books = {b["title"]: b["id"] for b in books}
        self.book_box.configure(values=[_ALL_BOOKS] + sorted(self.books))
        current = next((title for title, ident in self.books.items() if ident == self.book_id), _ALL_BOOKS)
        self.book_box.set(current)
        self._render()

    def _book_chosen(self, title: str) -> None:
        self.book_id = self.books.get(title)
        self.refresh()

    def _clear(self) -> None:
        self._cards = {}
        for child in self.list.winfo_children():
            child.destroy()

    def _message(self, text: str, error: bool = False) -> None:
        self._clear()
        ctk.CTkLabel(self.list, text=text, text_color=theme.DANGER if error else theme.TEXT_2, wraplength=700).grid(
            row=0, column=0, pady=40)
        if error:
            ctk.CTkButton(self.list, text="Thử lại", width=100, command=self.refresh).grid(row=1, column=0)

    def _render(self) -> None:
        self.shown = [n for n in self.notes if matches_quote(n, self.search.get())]
        self.play_btn.configure(state="normal" if self.shown else "disabled")
        if not self.shown:
            filtered = bool(self.search.get().strip()) or self.book_id is not None or self._tag() is not None
            return self._message("Không có trích dẫn phù hợp. Thử bỏ bớt bộ lọc." if filtered else
                                 "Chưa có trích dẫn nào. Khi nghe một đoạn hay, bấm “⭐ Đánh dấu đoạn này” (phím B) trong Phòng Đọc.")
        self._clear()
        for row, note in enumerate(self.shown):
            self._card(row, note)

    # -- one quote ----------------------------------------------------------------------------------------

    def _card(self, row: int, note: dict[str, Any]) -> None:
        card = ctk.CTkFrame(self.list, border_width=1, border_color=theme.BORDER, corner_radius=16)
        card.grid(row=row, column=0, sticky="ew", pady=6)
        card.columnconfigure(0, weight=1)
        self._cards[note["id"]] = card
        head = " · ".join(filter(None, [emotion_label(note["emotion_tag"]).upper(), note["book_title"],
                                        f"câu {note['sentence_index'] + 1}", format_datetime(note["created_at"])]))
        ctk.CTkLabel(card, text=head, anchor="w", text_color=theme.ACCENT if note["emotion_tag"] else theme.MUTED,
                     font=theme.font(11, "bold" if note["emotion_tag"] else "normal")).grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 0))
        if note["context_before"]:
            ctk.CTkLabel(card, text="…" + note["context_before"], anchor="w", justify="left", wraplength=760,
                         text_color=theme.MUTED, font=theme.font(12, serif=True)).grid(row=1, column=0, sticky="ew", padx=16)
        ctk.CTkLabel(card, text=f"“{note['excerpt']}”", anchor="w", justify="left", wraplength=760,
                     font=theme.font(17, serif=True)).grid(row=2, column=0, sticky="ew", padx=16, pady=2)
        if note["context_after"]:
            ctk.CTkLabel(card, text=note["context_after"] + "…", anchor="w", justify="left", wraplength=760,
                         text_color=theme.MUTED, font=theme.font(12, serif=True)).grid(row=3, column=0, sticky="ew", padx=16)
        if note["note_text"]:
            ctk.CTkLabel(card, text=f"📝 {note['note_text']}", anchor="w", justify="left", wraplength=760).grid(
                row=4, column=0, sticky="ew", padx=16, pady=(4, 0))
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.grid(row=5, column=0, sticky="w", padx=10, pady=10)
        for text, command, style in (
            ("▶ Nghe lại", lambda n=note: self._play_one(n), {}),
            ("Đến câu này", lambda n=note: self.ctx.app.open_in_reader(n["book_id"], n["book_title"], n["sentence_index"]), theme.SECONDARY),
            ("Sửa", lambda n=note: EditNoteDialog(self, self.ctx, n, self.refresh), theme.GHOST),
            ("Xóa", lambda n=note: self._delete(n), {**theme.GHOST, "text_color": theme.DANGER}),
        ):
            ctk.CTkButton(buttons, text=text, width=96, height=32, command=command, **style).pack(side="left", padx=4)

    def _pause_reader(self) -> None:
        if self.ctx.reader.is_playing:
            self.ctx.reader.toggle()  # the reader and the quotes share one sound output: never overlap

    def _play_one(self, note: dict[str, Any]) -> None:
        """"Nghe lại": play this quote (the quotes after it follow, like a playlist). Again on the same one stops."""
        if self._playing_id == note["id"]:
            return self.playlist.stop()
        self._pause_reader()
        self.playlist.start([n["id"] for n in self.shown], self.shown.index(note))

    def _toggle_playlist(self) -> None:
        if self.playlist.playing:
            return self.playlist.stop()
        self._pause_reader()
        self.playlist.start([n["id"] for n in self.shown], 0)

    def _playlist_changed(self, position: int | None) -> None:
        """Called on the UI thread: highlight the quote being played and show the controls."""
        if not self.winfo_exists():
            return
        if self._playing_id in self._cards:
            self._cards[self._playing_id].configure(border_color=theme.BORDER, fg_color=theme.SURFACE)
        self._playing_id = self.shown[position]["id"] if position is not None and position < len(self.shown) else None
        if self._playing_id in self._cards:
            self._cards[self._playing_id].configure(border_color=theme.ACCENT, fg_color=theme.ACCENT_SOFT)
        if position is None:
            self.play_btn.configure(text="▶ Phát liên tục")
            for widget in (self.progress_label, self.prev_btn, self.next_btn):
                widget.pack_forget()
        else:
            self.play_btn.configure(text="⏹ Dừng")
            self.progress_label.configure(text=f"Đang phát {position + 1} / {len(self.shown)}")
            for widget in (self.next_btn, self.prev_btn, self.progress_label):
                widget.pack_forget()
                widget.pack(side="right", padx=(0, 6))

    def _delete(self, note: dict[str, Any]) -> None:
        if not messagebox.askyesno("Xóa trích dẫn", "Xóa trích dẫn này và file âm thanh đã lưu của nó?", parent=self.winfo_toplevel()):
            return
        self.ctx.ui.run_in_thread(lambda: self.ctx.api.delete_note(note["id"]), lambda _r: self.refresh(),
                                  lambda exc: self.ctx.app.show_error(error_text(exc)))

    def shutdown(self) -> None:
        """Stop the playlist (the window is closing or the user left for another screen)."""
        self.playlist.stop(notify=False)
