"""S10 – Khám phá: the public catalogue. Add a system book to the shelf, or open it straight away."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from ui import theme
from ui.category_chips import CategoryChips
from ui.common import AppContext, LatestRequest, error_text
from ui.dialogs import UploadDialog
from ui.images import CoverView
from ui.viewmodels import EXPLORE_SORTS, format_duration, format_number


def book_card(parent: ctk.CTkFrame, ctx: AppContext, index: int, book: dict[str, Any],
              on_listen: Callable[[dict[str, Any]], None], on_add: Callable[[dict[str, Any]], None]) -> None:
    """A public book as a card (two per row): used by Khám phá and Gợi Ý. A book that carries `reasons` (Gợi Ý) also shows
    why it was suggested and how long it takes."""
    card = ctk.CTkFrame(parent, border_width=1, border_color=theme.BORDER, corner_radius=16)
    card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=6, pady=6)
    card.columnconfigure(1, weight=1)
    CoverView(card, ctx, book["title"], book.get("cover_url"), size=(78, 104)).grid(row=0, column=0, rowspan=2, padx=12, pady=12)
    info = ctk.CTkFrame(card, fg_color="transparent")
    info.grid(row=0, column=1, sticky="nsew", pady=(12, 0))
    info.columnconfigure(0, weight=1)
    category = (book.get("category") or {}).get("name")
    if category:
        ctk.CTkLabel(info, text=category.upper(), anchor="w", text_color=theme.ACCENT, font=theme.font(10, "bold")).pack(fill="x")
    ctk.CTkLabel(info, text=book["title"], anchor="w", justify="left", wraplength=230, font=theme.font(14, "bold")).pack(fill="x")
    author = book.get("author") if book.get("author") and book["author"] != "Unknown" else "Sách hệ thống"
    ctk.CTkLabel(info, text=author, anchor="w", text_color=theme.MUTED, font=theme.font(12)).pack(fill="x")
    meta = f"{format_number(book['total_chapters'])} chương · {format_number(book['total_words'])} từ"
    if book.get("estimated_minutes"):
        meta += f" · {format_duration(book['estimated_minutes'])}"
    ctk.CTkLabel(info, text=meta, anchor="w", text_color=theme.MUTED, font=theme.font(11)).pack(fill="x")
    for reason in book.get("reasons") or []:
        ctk.CTkLabel(info, text=f"✦ {reason}", anchor="w", justify="left", wraplength=230, text_color=theme.ACCENT,
                     font=theme.font(11)).pack(fill="x")
    actions = ctk.CTkFrame(card, fg_color="transparent")
    actions.grid(row=1, column=1, sticky="ew", pady=(0, 12))
    ctk.CTkButton(actions, text="Nghe ngay", width=96, height=32, command=lambda: on_listen(book)).pack(side="left")
    if book.get("on_shelf"):
        ctk.CTkLabel(actions, text="✓ Trong kệ", text_color=theme.SUCCESS, font=theme.font(12, "bold")).pack(side="left", padx=10)
    else:
        ctk.CTkButton(actions, text="+ Thêm vào kệ", width=104, height=32, command=lambda: on_add(book),
                      **theme.SECONDARY).pack(side="left", padx=(6, 0))


class ExploreTab(ctk.CTkFrame):
    def __init__(self, master: tk.Misc, ctx: AppContext):
        super().__init__(master, fg_color="transparent")
        self.ctx = ctx
        self.books: list[dict[str, Any]] = []
        self._search_job: str | None = None
        self._requests = LatestRequest()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(titles, text="Khám phá", anchor="w", font=theme.font(26, "bold")).pack(anchor="w")
        ctk.CTkLabel(titles, text="Kho sách chung của hệ thống. Thêm vào kệ để lưu tiến độ nghe riêng của bạn.",
                     anchor="w", text_color=theme.MUTED).pack(anchor="w")
        self.upload_btn = ctk.CTkButton(header, text="+ Thêm sách hệ thống", command=self._upload)
        self.upload_btn.grid(row=0, column=1, sticky="e")
        if ctx.user.get("role") != "admin":
            self.upload_btn.grid_remove()

        self.chips = CategoryChips(self, ctx.app.pick_category)
        self.chips.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=2, column=0, sticky="ew", pady=4)
        toolbar.columnconfigure(0, weight=1)
        self.search = ctk.CTkEntry(toolbar, placeholder_text="🔍 Tìm theo tên sách hoặc tác giả…")
        self.search.grid(row=0, column=0, sticky="ew")
        self.search.bind("<KeyRelease>", lambda _e: self._search_changed())
        self.sort_box = ctk.CTkComboBox(toolbar, values=[label for _, label in EXPLORE_SORTS], width=150,
                                        state="readonly", command=lambda _v: self.refresh())
        self.sort_box.set(EXPLORE_SORTS[0][1])
        self.sort_box.grid(row=0, column=1, padx=(6, 0))

        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list.grid(row=3, column=0, sticky="nsew", pady=(4, 8))
        self.list.columnconfigure(0, weight=1)
        self.list.columnconfigure(1, weight=1)

    # -- data ---------------------------------------------------------------------------------------------

    def _search_changed(self) -> None:
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(300, self.refresh)

    def refresh(self) -> None:
        self._search_job = None
        self._message("Đang tải…")
        query, category = self.search.get(), self.ctx.app.category
        sort = next((key for key, label in EXPLORE_SORTS if label == self.sort_box.get()), "newest")
        token = self._requests.start()
        self.ctx.ui.run_in_thread(lambda: self.ctx.api.explore_books(query, category, sort),
                                  self._requests.wrap(token, self._loaded),
                                  self._requests.wrap(token, lambda exc: self._message(error_text(exc), error=True)))

    def _loaded(self, books: list[dict[str, Any]]) -> None:
        self.books = books
        if not books:
            filtered = bool(self.search.get().strip()) or self.ctx.app.category is not None
            admin = self.ctx.user.get("role") == "admin"
            return self._message(
                "Không tìm thấy sách phù hợp." if filtered else
                "Chưa có sách hệ thống nào. " + ("Dùng “+ Thêm sách hệ thống” để đăng cuốn đầu tiên." if admin
                                                 else "Quản trị viên sẽ đăng sách mẫu ở đây."))
        self._clear()
        for index, book in enumerate(books):
            self._card(index, book)

    def _clear(self) -> None:
        for child in self.list.winfo_children():
            child.destroy()

    def _message(self, text: str, error: bool = False) -> None:
        self._clear()
        ctk.CTkLabel(self.list, text=text, text_color=theme.DANGER if error else theme.TEXT_2, wraplength=700).grid(
            row=0, column=0, columnspan=2, pady=40)
        if error:
            ctk.CTkButton(self.list, text="Thử lại", width=100, command=self.refresh).grid(row=1, column=0, columnspan=2)

    # -- one book -----------------------------------------------------------------------------------------

    def _card(self, index: int, book: dict[str, Any]) -> None:
        book_card(self.list, self.ctx, index, book, on_listen=self._listen, on_add=self._add)

    def _add(self, book: dict[str, Any], then_listen: bool = False) -> None:
        def done(_result: Any) -> None:
            if then_listen:
                self.ctx.app.open_in_reader(book["id"], book["title"])
            else:
                self.ctx.app.toast(f'Đã thêm "{book["title"]}" vào kệ.')
            self.refresh()

        self.ctx.ui.run_in_thread(lambda: self.ctx.api.add_to_shelf(book["id"]), done,
                                  lambda exc: self.ctx.app.show_error(error_text(exc)))

    def _listen(self, book: dict[str, Any]) -> None:
        if book.get("on_shelf"):
            self.ctx.app.open_in_reader(book["id"], book["title"])
        else:
            self._add(book, then_listen=True)

    def _upload(self) -> None:
        def uploaded(result: dict[str, Any]) -> None:
            self.ctx.app.toast(f'Đã đăng "{result["title"]}" vào Khám phá.')
            self.refresh()

        UploadDialog(self, self.ctx, on_done=uploaded, default_public=True)
