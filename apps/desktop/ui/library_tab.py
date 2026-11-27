"""S01 – Kệ sách của tôi: tabs by reading status. (The quotes have their own screen, quotes_tab.py.)"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

from ui import theme
from ui.category_chips import CategoryChips
from ui.common import AppContext, error_text
from ui.dialogs import EditBookDialog, ExportDialog, UploadDialog
from ui.images import CoverView
from ui.viewmodels import (
    SHELF_TABS,
    SORT_OPTIONS,
    SOURCE_OPTIONS,
    format_datetime,
    format_number,
    pick_initial_tab,
    play_label,
    progress_fraction,
)


class LibraryTab(ctk.CTkFrame):
    def __init__(self, master: tk.Misc, ctx: AppContext):
        super().__init__(master, fg_color="transparent")
        self.ctx = ctx
        self.books: list[dict[str, Any]] = []
        self.counts: dict[str, int] = {}
        self.tab: str | None = None  # a key of SHELF_TABS; None until the first counts pick one
        self._search_job: str | None = None
        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(titles, text="Kệ sách của tôi", anchor="w", font=theme.font(26, "bold")).pack(anchor="w")
        ctk.CTkLabel(titles, text="Sách của bạn và sách hệ thống bạn đã thêm, theo tiến độ nghe.", anchor="w",
                     text_color=theme.MUTED).pack(anchor="w")
        self.add_btn = ctk.CTkButton(header, text="+ Thêm tài liệu", command=self._add)
        self.add_btn.grid(row=0, column=1, sticky="e")

        self.switch = ctk.CTkSegmentedButton(self, values=[label for _, label in SHELF_TABS], command=self._switch)
        self.switch.grid(row=1, column=0, sticky="w", pady=(0, 8))

        self.chips = CategoryChips(self, ctx.app.pick_category)
        self.chips.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        self.toolbar = ctk.CTkFrame(self, fg_color="transparent")
        self.toolbar.grid(row=3, column=0, sticky="ew", pady=4)
        self.toolbar.columnconfigure(0, weight=1)
        self.search = ctk.CTkEntry(self.toolbar, placeholder_text="🔍 Tìm theo tên sách hoặc tác giả…")
        self.search.grid(row=0, column=0, sticky="ew")
        self.search.bind("<KeyRelease>", lambda _e: self._search_changed())
        self.source_box = ctk.CTkComboBox(self.toolbar, values=[label for _, label in SOURCE_OPTIONS], width=150,
                                          state="readonly", command=lambda _v: self.refresh())
        self.source_box.set(SOURCE_OPTIONS[0][1])
        self.source_box.grid(row=0, column=1, padx=6)
        self.sort_box = ctk.CTkComboBox(self.toolbar, values=[label for _, label in SORT_OPTIONS], width=150,
                                        state="readonly", command=lambda _v: self.refresh())
        self.sort_box.set(SORT_OPTIONS[0][1])
        self.sort_box.grid(row=0, column=2)

        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list.grid(row=4, column=0, sticky="nsew", pady=(4, 8))
        self.list.columnconfigure(0, weight=1)

    # -- data -----------------------------------------------------------------------------------------

    def _filters(self) -> dict[str, Any]:
        source = next((key for key, label in SOURCE_OPTIONS if label == self.source_box.get()), "all")
        sort = next((key for key, label in SORT_OPTIONS if label == self.sort_box.get()), "recent")
        return {"q": self.search.get(), "category": self.ctx.app.category, "source": source, "sort": sort}

    def _search_changed(self) -> None:
        """Ask the backend after the user stops typing (not on every key)."""
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(300, self.refresh)

    def refresh(self) -> None:
        self._search_job = None
        self._show_message("Đang tải…")
        filters = self._filters()
        tab = self.tab
        need_resume = not self.ctx.app.resumed

        def work() -> dict[str, Any]:
            api = self.ctx.api
            counts = api.shelf_counts(filters["q"], filters["category"], filters["source"])
            chosen = tab or pick_initial_tab(counts)
            return {"tab": chosen, "counts": counts, "books": api.list_books(status=chosen, **filters),
                    "shelf": api.list_books() if need_resume else None}

        self.ctx.ui.run_in_thread(work, self._loaded, lambda exc: self._show_message(error_text(exc), error=True))

    def _loaded(self, result: dict[str, Any]) -> None:
        self.tab, self.counts = result["tab"], result["counts"]
        self.books = result["books"]
        labels = [f"{label} ({self.counts.get(key, 0)})" for key, label in SHELF_TABS]
        self.switch.configure(values=labels)
        self.switch.set(labels[[key for key, _ in SHELF_TABS].index(self.tab)])
        self._render_books()
        if result["shelf"] is not None:
            self.ctx.app.on_library_loaded(result["shelf"])

    # -- view switching -----------------------------------------------------------------------------------

    def _switch(self, label: str) -> None:
        labels = [text for _, text in SHELF_TABS]
        index = next((i for i, text in enumerate(labels) if label.startswith(text)), 0)
        self.tab = SHELF_TABS[index][0]
        self.refresh()

    def _clear(self) -> None:
        for child in self.list.winfo_children():
            child.destroy()

    def _show_message(self, text: str, error: bool = False) -> None:
        self._clear()
        ctk.CTkLabel(self.list, text=text, text_color=theme.DANGER if error else theme.TEXT_2,
                     wraplength=700).grid(row=0, column=0, pady=40)
        if error:
            ctk.CTkButton(self.list, text="Thử lại", width=100, command=self.refresh).grid(row=1, column=0)

    # -- S01: the shelf -----------------------------------------------------------------------------------

    def _render_books(self) -> None:
        if not self.books:
            filtered = bool(self.search.get().strip()) or self.ctx.app.category is not None or self.source_box.get() != SOURCE_OPTIONS[0][1]
            if filtered:
                return self._show_message("Không tìm thấy sách phù hợp. Thử bỏ bớt bộ lọc, hoặc đổi sang tab khác.")
            if self.tab == "reading" and sum(self.counts.get(k, 0) for k in ("unread", "completed", "favorite")):
                return self._show_message("Bạn chưa nghe dở cuốn nào. Mở tab “Chưa nghe” để bắt đầu một cuốn.")
            return self._show_message("Chưa có sách nào ở đây. Thêm tài liệu của bạn, hoặc vào “Khám phá” để chọn sách hệ thống.")
        self._clear()
        for row, book in enumerate(self.books):
            self._book_card(row, book)

    def _book_card(self, row: int, book: dict[str, Any]) -> None:
        card = ctk.CTkFrame(self.list, border_width=1, border_color=theme.BORDER, corner_radius=16)
        card.grid(row=row, column=0, sticky="ew", pady=6)
        card.columnconfigure(1, weight=1)
        progress = book.get("progress")
        fraction = progress_fraction(progress)
        status = (progress or {}).get("status", "unread")
        mine = book.get("is_mine", True)

        CoverView(card, self.ctx, book["title"], book.get("cover_url")).grid(
            row=0, column=0, rowspan=2, padx=14, pady=14)
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.grid(row=0, column=1, sticky="nsew", pady=(14, 0))
        info.columnconfigure(0, weight=1)
        chips = " · ".join(filter(None, [(book.get("category") or {}).get("name"), "Hệ thống" if book.get("is_public") else "",
                                         "✔ Đã xong" if status == "completed" else ""]))
        if chips:
            ctk.CTkLabel(info, text=chips.upper(), anchor="w", text_color=theme.ACCENT, font=theme.font(10, "bold")).grid(
                row=0, column=0, sticky="ew")
        ctk.CTkLabel(info, text=book["title"], anchor="w", justify="left", wraplength=420,
                     font=theme.font(16, "bold")).grid(row=1, column=0, sticky="ew")
        author = book.get("author") if book.get("author") and book["author"] != "Unknown" else ""
        ctk.CTkLabel(info, anchor="w", text_color=theme.MUTED, font=theme.font(12),
                     text=" · ".join(filter(None, [author, f"{format_number(book['total_sentences'])} câu",
                                                   f"{format_number(book['total_words'])} từ"]))).grid(row=2, column=0, sticky="ew")
        bar = ctk.CTkProgressBar(info, height=6)
        bar.set(fraction)
        bar.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        last = format_datetime((progress or {}).get("last_read_at")) if fraction > 0 else "Chưa nghe"
        ctk.CTkLabel(info, anchor="w", text_color=theme.MUTED, font=theme.font(12),
                     text=f"{fraction * 100:.0f}% · {last}").grid(row=4, column=0, sticky="ew")

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=1, column=1, sticky="ew", pady=(0, 12))
        ctk.CTkButton(actions, width=140, height=34, text=play_label(status),
                      command=lambda: self.ctx.app.open_in_reader(book["id"], book["title"])).pack(side="left")
        favorite = bool((progress or {}).get("is_favorite"))
        buttons: list[tuple[str, Any, dict[str, Any]]] = [
            ("♥" if favorite else "♡", lambda: self._act(self.ctx.api.set_favorite, book["id"], not favorite),
             {**theme.GHOST, "text_color": theme.DANGER if favorite else theme.TEXT_2, "width": 36}),
        ]
        if status == "reading":
            buttons.append(("✔ Đã nghe xong", lambda: self._act(self.ctx.api.set_read_status, book["id"], "completed"), theme.GHOST))
        elif status == "completed":
            buttons.append(("↺ Nghe lại", lambda: self._act(self.ctx.api.set_read_status, book["id"], "unread"), theme.GHOST))
        if mine:
            buttons.append(("Sửa", lambda: self._edit_book(book), theme.GHOST))
        buttons += [
            ("Trích dẫn", lambda: self.ctx.app.show_quotes_for(book["id"]), theme.GHOST),
            ("Xuất", lambda: ExportDialog(self, self.ctx, book), theme.GHOST),
            ("Xóa" if mine else "Gỡ khỏi kệ", lambda: self._remove_book(book),
             {**theme.GHOST, "text_color": theme.DANGER}),
        ]
        for text, command, style in buttons:
            style = {"width": 64, **style}
            ctk.CTkButton(actions, text=text, height=34, command=command, **style).pack(side="left", padx=(6, 0))

    def _act(self, call: Any, *args: Any) -> None:
        """Run a shelf change (favourite, status) in the background, then redraw."""
        self.ctx.ui.run_in_thread(lambda: call(*args), lambda _r: self.refresh(),
                                  lambda exc: self.ctx.app.show_error(error_text(exc)))

    def _add(self) -> None:
        UploadDialog(self, self.ctx, on_done=self._uploaded)

    def _uploaded(self, result: dict[str, Any]) -> None:
        self.ctx.app.toast(f'Đã thêm "{result["title"]}" ({format_number(result["total_sentences"])} câu)')
        self.tab = "unread"
        self.refresh()

    def _edit_book(self, book: dict[str, Any]) -> None:
        def saved(result: dict[str, Any]) -> None:
            self.ctx.app.on_book_renamed(result["id"], result["title"])
            self.ctx.app.toast(f'Đã lưu "{result["title"]}".')
            self.refresh()

        EditBookDialog(self, self.ctx, book, on_saved=saved)

    def _remove_book(self, book: dict[str, Any]) -> None:
        if not book.get("is_mine", True):  # a public book: just take it off the shelf
            self.ctx.ui.run_in_thread(lambda: self.ctx.api.remove_from_shelf(book["id"]),
                                      lambda _r: (self.ctx.app.toast(f'Đã gỡ "{book["title"]}" khỏi kệ.'), self.refresh()),
                                      lambda exc: self.ctx.app.show_error(error_text(exc)))
            return
        if not messagebox.askyesno(
            "Xóa tài liệu",
            f'Xóa "{book["title"]}"? Ghi chú, tiến độ và ảnh bìa của tài liệu cũng bị xóa.', parent=self.winfo_toplevel()):
            return
        if self.ctx.reader.book and self.ctx.reader.book.book_id == book["id"]:
            self.ctx.app.close_reader_book()
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.delete_book(book["id"]), lambda _: self.refresh(),
            lambda exc: self.ctx.app.show_error(error_text(exc)))
