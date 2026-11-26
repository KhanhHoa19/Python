"""S01 – Thư viện tài liệu and S06 – Ghi chú âm thanh (two sub-views of one tab)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

from ui.common import AppContext, error_text
from ui.dialogs import EditNoteDialog, ExportDialog, UploadDialog
from ui.viewmodels import (
    SORT_OPTIONS,
    filter_and_sort_books,
    format_datetime,
    format_number,
    normalize_text,
    progress_fraction,
)

_ALL_BOOKS = "Tất cả"


class LibraryTab(ctk.CTkFrame):
    def __init__(self, master: tk.Misc, ctx: AppContext):
        super().__init__(master, fg_color="transparent")
        self.ctx = ctx
        self.books: list[dict[str, Any]] = []
        self.notes: list[dict[str, Any]] = []
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self.switch = ctk.CTkSegmentedButton(self, values=["Tài liệu", "Ghi chú"], command=self._switch)
        self.switch.set("Tài liệu")
        self.switch.grid(row=0, column=0, pady=(10, 4))

        self.toolbar = ctk.CTkFrame(self, fg_color="transparent")
        self.toolbar.grid(row=1, column=0, sticky="ew", padx=12, pady=4)
        self.toolbar.columnconfigure(0, weight=1)
        self.search = ctk.CTkEntry(self.toolbar, placeholder_text="🔍 Tìm theo tên…")
        self.search.grid(row=0, column=0, sticky="ew")
        self.search.bind("<KeyRelease>", lambda _e: self._render())
        self.sort_box = ctk.CTkComboBox(self.toolbar, values=list(SORT_OPTIONS), width=150, state="readonly",
                                        command=lambda _v: self._render())
        self.sort_box.set(SORT_OPTIONS[0])
        self.sort_box.grid(row=0, column=1, padx=6)
        self.book_filter = ctk.CTkComboBox(self.toolbar, values=[_ALL_BOOKS], width=200, state="readonly",
                                           command=lambda _v: self._render())
        self.book_filter.set(_ALL_BOOKS)
        self.add_btn = ctk.CTkButton(self.toolbar, text="+ Thêm tài liệu", command=self._add)
        self.add_btn.grid(row=0, column=3)

        self.list = ctk.CTkScrollableFrame(self)
        self.list.grid(row=2, column=0, sticky="nsew", padx=12, pady=(4, 12))
        self.list.columnconfigure(0, weight=1)
        self.message = ctk.CTkLabel(self.list, text="")
        self._mode = "books"

    # -- data -----------------------------------------------------------------------------------------

    def refresh(self) -> None:
        self._show_message("Đang tải…")

        def work() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            books = self.ctx.api.list_books()
            for book in books:
                try:
                    book["bookmark"] = self.ctx.api.get_bookmark(book["id"])
                except Exception:
                    book["bookmark"] = None
            return books, self.ctx.api.list_notes()

        self.ctx.ui.run_in_thread(work, self._loaded, lambda exc: self._show_message(error_text(exc), error=True))

    def _loaded(self, result: tuple[list[dict[str, Any]], list[dict[str, Any]]]) -> None:
        self.books, self.notes = result
        self.book_filter.configure(values=[_ALL_BOOKS] + [b["title"] for b in self.books])
        if self.book_filter.get() not in [_ALL_BOOKS] + [b["title"] for b in self.books]:
            self.book_filter.set(_ALL_BOOKS)
        self._render()
        self.ctx.app.on_library_loaded(self.books)

    def show_notes_for(self, title: str) -> None:
        self.switch.set("Ghi chú")
        self.book_filter.set(title)
        self._switch("Ghi chú")

    # -- view switching -----------------------------------------------------------------------------------

    def _switch(self, which: str) -> None:
        self._mode = "notes" if which == "Ghi chú" else "books"
        if self._mode == "notes":
            self.sort_box.grid_remove()
            self.add_btn.grid_remove()
            self.book_filter.grid(row=0, column=2, padx=6)
            self.search.configure(placeholder_text="🔍 Tìm trong ghi chú…")
        else:
            self.book_filter.grid_remove()
            self.sort_box.grid()
            self.add_btn.grid()
            self.search.configure(placeholder_text="🔍 Tìm theo tên…")
        self.search.delete(0, "end")
        self._render()

    def _clear(self) -> None:
        for child in self.list.winfo_children():
            child.destroy()

    def _show_message(self, text: str, error: bool = False) -> None:
        self._clear()
        ctk.CTkLabel(self.list, text=text, text_color="#d64545" if error else ("gray20", "gray80"),
                     wraplength=700).grid(row=0, column=0, pady=40)
        if error:
            ctk.CTkButton(self.list, text="Thử lại", width=100, command=self.refresh).grid(row=1, column=0)

    def _render(self) -> None:
        if self._mode == "books":
            self._render_books()
        else:
            self._render_notes()

    # -- S01: documents -----------------------------------------------------------------------------------

    def _render_books(self) -> None:
        books = filter_and_sort_books(self.books, self.search.get(), self.sort_box.get())
        if not self.books:
            return self._show_message("Chưa có tài liệu nào. Bấm “+ Thêm tài liệu” để bắt đầu.")
        if not books:
            return self._show_message("Không tìm thấy tài liệu phù hợp.")
        self._clear()
        for row, book in enumerate(books):
            self._book_card(row, book)

    def _book_card(self, row: int, book: dict[str, Any]) -> None:
        card = ctk.CTkFrame(self.list)
        card.grid(row=row, column=0, sticky="ew", pady=4)
        card.columnconfigure(0, weight=1)
        bookmark = book.get("bookmark")
        fraction = progress_fraction(bookmark)
        ctk.CTkLabel(card, text=book["title"], anchor="w", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, sticky="ew", padx=12, pady=(8, 0))
        author = f" · {book['author']}" if book.get("author") and book["author"] != "Unknown" else ""
        ctk.CTkLabel(card, anchor="w", text_color=("gray35", "gray65"),
                     text=f"{format_number(book['total_sentences'])} câu · {format_number(book['total_words'])} từ{author}"
                     ).grid(row=1, column=0, sticky="ew", padx=12)
        bar = ctk.CTkProgressBar(card)
        bar.set(fraction)
        bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 0))
        last = format_datetime(bookmark.get("last_read_at")) if bookmark and fraction > 0 else "Chưa đọc"
        ctk.CTkLabel(card, anchor="w", text=f"{fraction * 100:.0f}% · Đọc: {last}").grid(
            row=3, column=0, sticky="ew", padx=12, pady=(0, 6))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=0, column=1, rowspan=4, padx=10)
        ctk.CTkButton(actions, width=130, text="Tiếp tục đọc" if fraction > 0 else "Bắt đầu đọc",
                      command=lambda: self.ctx.app.open_in_reader(book["id"], book["title"])).pack(pady=2)
        row_buttons = ctk.CTkFrame(actions, fg_color="transparent")
        row_buttons.pack()
        for text, command in (
            ("Ghi chú", lambda: self.show_notes_for(book["title"])),
            ("Xuất", lambda: ExportDialog(self, self.ctx, book)),
        ):
            ctk.CTkButton(row_buttons, text=text, width=62, fg_color="gray40", command=command).pack(side="left", padx=1)
        ctk.CTkButton(actions, text="Xóa", width=130, fg_color="#d64545", command=lambda: self._delete_book(book)).pack(pady=2)

    def _add(self) -> None:
        UploadDialog(self, self.ctx, on_done=self._uploaded)

    def _uploaded(self, result: dict[str, Any]) -> None:
        self.ctx.app.toast(f'Đã thêm "{result["title"]}" ({format_number(result["total_sentences"])} câu)')
        self.refresh()

    def _delete_book(self, book: dict[str, Any]) -> None:
        if not messagebox.askyesno(
            "Xóa tài liệu",
            f'Xóa "{book["title"]}"? Ghi chú và lịch sử đọc của tài liệu cũng bị xóa.', parent=self.winfo_toplevel()):
            return
        if self.ctx.reader.book and self.ctx.reader.book.book_id == book["id"]:
            self.ctx.app.close_reader_book()
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.delete_book(book["id"]), lambda _: self.refresh(),
            lambda exc: self.ctx.app.show_error(error_text(exc)))

    # -- S06: notes -----------------------------------------------------------------------------------------

    def _render_notes(self) -> None:
        needle = normalize_text(self.search.get().strip())
        chosen = self.book_filter.get()
        notes = [
            n for n in self.notes
            if (chosen == _ALL_BOOKS or n["book_title"] == chosen)
            and needle in normalize_text(f"{n['excerpt']} {n['note_text']}")
        ]
        if not self.notes:
            return self._show_message("Chưa có ghi chú. Hãy bôi đen một đoạn trong Phòng Đọc để tạo.")
        if not notes:
            return self._show_message("Không có ghi chú phù hợp.")
        self._clear()
        for row, note in enumerate(notes):
            self._note_card(row, note)

    def _note_card(self, row: int, note: dict[str, Any]) -> None:
        card = ctk.CTkFrame(self.list)
        card.grid(row=row, column=0, sticky="ew", pady=4)
        card.columnconfigure(0, weight=1)
        ctk.CTkLabel(card, anchor="w", text_color=("gray35", "gray65"),
                     text=f"📄 {note['book_title']} · câu {note['sentence_index'] + 1} · {format_datetime(note['created_at'])}"
                     ).grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 0))
        ctk.CTkLabel(card, anchor="w", justify="left", wraplength=720, text=f"“{note['excerpt']}”").grid(
            row=1, column=0, sticky="ew", padx=12)
        if note["note_text"]:
            ctk.CTkLabel(card, anchor="w", justify="left", wraplength=720, text=f"📝 {note['note_text']}").grid(
                row=2, column=0, sticky="ew", padx=12)
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.grid(row=3, column=0, sticky="w", padx=8, pady=6)
        for text, command, color in (
            ("▶ Nghe lại", lambda: self._play_note(note), None),
            ("Đến câu này", lambda: self.ctx.app.open_in_reader(note["book_id"], note["book_title"], note["sentence_index"]), None),
            ("Sửa", lambda: EditNoteDialog(self, self.ctx, note, self.refresh), "gray40"),
            ("Xóa", lambda: self._delete_note(note), "#d64545"),
        ):
            kwargs = {"fg_color": color} if color else {}
            ctk.CTkButton(buttons, text=text, width=96, command=command, **kwargs).pack(side="left", padx=3)

    def _play_note(self, note: dict[str, Any]) -> None:
        if self.ctx.reader.is_playing:
            self.ctx.reader.toggle()  # pause the reader so the two sounds do not overlap

        def work() -> None:
            data, ext = self.ctx.api.note_audio(note["id"])
            self.ctx.output.play(data, ext)

        self.ctx.ui.run_in_thread(work, None, lambda exc: self.ctx.app.show_error(error_text(exc)))

    def _delete_note(self, note: dict[str, Any]) -> None:
        if not messagebox.askyesno("Xóa ghi chú", "Xóa ghi chú này?", parent=self.winfo_toplevel()):
            return
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.delete_note(note["id"]), lambda _: self.refresh(),
            lambda exc: self.ctx.app.show_error(error_text(exc)))
