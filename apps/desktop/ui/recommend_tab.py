"""S12 – Gợi Ý: books suggested for this reader, with the reasons; filter by mood and length."""

from __future__ import annotations

import tkinter as tk
from typing import Any

import customtkinter as ctk

from ui import theme
from ui.common import AppContext, LatestRequest, error_text
from ui.explore_tab import book_card
from ui.viewmodels import DURATION_OPTIONS, describe_filters, toggle_slug

_ALL_MOODS = "Tất cả"


class RecommendTab(ctk.CTkFrame):
    def __init__(self, master: tk.Misc, ctx: AppContext):
        super().__init__(master, fg_color="transparent")
        self.ctx = ctx
        self.data: dict[str, Any] = {}
        self.books: list[dict[str, Any]] = []
        self.mood: str | None = None  # a mood id
        self.picked: list[str] = []  # slugs ticked in the picker
        self.editing = False
        self._requests = LatestRequest()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)

        titles = ctk.CTkFrame(self, fg_color="transparent")
        titles.grid(row=0, column=0, sticky="w", pady=(0, 10))
        ctk.CTkLabel(titles, text="Gợi ý cho bạn", anchor="w", font=theme.font(26, "bold")).pack(anchor="w")
        ctk.CTkLabel(titles, text="Sách hệ thống hợp với bạn hôm nay, kèm lý do vì sao.", anchor="w",
                     text_color=theme.MUTED).pack(anchor="w")

        self.prefs = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=14, border_width=1, border_color=theme.BORDER_STRONG)
        self.prefs.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.prefs.grid_remove()
        self.summary = ctk.CTkFrame(self, fg_color="transparent")
        self.summary.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.grid(row=2, column=0, sticky="ew")
        self.mood_box = ctk.CTkSegmentedButton(filters, values=[_ALL_MOODS], command=self._mood_chosen)
        self.mood_box.set(_ALL_MOODS)
        self.mood_box.pack(anchor="w", pady=(0, 6))
        self.duration_box = ctk.CTkSegmentedButton(filters, values=[label for label, _ in DURATION_OPTIONS],
                                                   command=lambda _v: self.refresh())
        self.duration_box.set(DURATION_OPTIONS[0][0])
        self.duration_box.pack(anchor="w")
        self.filter_label = ctk.CTkLabel(self, text="", anchor="w", text_color=theme.MUTED)
        self.filter_label.grid(row=3, column=0, sticky="ew", pady=(6, 0))

        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list.grid(row=4, column=0, sticky="nsew", pady=(4, 8))
        self.list.columnconfigure(0, weight=1)
        self.list.columnconfigure(1, weight=1)

    # -- data ---------------------------------------------------------------------------------------------

    def _minutes(self) -> int | None:
        return next((m for label, m in DURATION_OPTIONS if label == self.duration_box.get()), None)

    def refresh(self) -> None:
        self._message("Đang tải…")
        mood, minutes = self.mood, self._minutes()
        token = self._requests.start()
        self.ctx.ui.run_in_thread(lambda: self.ctx.api.recommendations(mood, minutes),
                                  self._requests.wrap(token, self._loaded),
                                  self._requests.wrap(token, lambda exc: self._message(error_text(exc), error=True)))

    def _loaded(self, data: dict[str, Any]) -> None:
        self.data, self.books = data, data["items"]
        labels = [_ALL_MOODS] + [m["label"] for m in data["moods"]]
        self.mood_box.configure(values=labels)
        current = next((m["label"] for m in data["moods"] if m["id"] == self.mood), _ALL_MOODS)
        self.mood_box.set(current)
        self._show_summary()
        label = next((m["label"] for m in data["moods"] if m["id"] == self.mood), None)
        duration_label = self.duration_box.get()
        self.filter_label.configure(text=describe_filters(label, duration_label, self._minutes()))
        self._show_books()

    def _mood_chosen(self, label: str) -> None:
        moods = self.data.get("moods", [])
        chosen = next((m["id"] for m in moods if m["label"] == label), None)
        self.mood = None if chosen == self.mood else chosen  # clicking the chosen mood again clears it
        self.refresh()

    # -- favourite categories (first-time question and later edits) ------------------------------------------

    def _show_summary(self) -> None:
        for child in self.summary.winfo_children():
            child.destroy()
        if not self.data.get("onboarded") or self.editing:
            self.summary.grid_remove()
            self._show_picker()
            return
        self.prefs.grid_remove()
        self.summary.grid()
        names = {c["slug"]: c["name"] for c in self.ctx.app.categories}
        favorites = [names.get(s, s) for s in self.data["favorite_categories"]]
        line = ctk.CTkFrame(self.summary, fg_color="transparent")
        line.pack(anchor="w", fill="x")
        ctk.CTkLabel(line, text="Thể loại yêu thích:", text_color=theme.MUTED).pack(side="left")
        ctk.CTkLabel(line, text=" · ".join(favorites) if favorites else "chưa chọn (dựa vào lịch sử nghe)",
                     font=theme.font(13, "bold") if favorites else theme.font(13), text_color=theme.TEXT if favorites else theme.MUTED
                     ).pack(side="left", padx=8)
        ctk.CTkButton(line, text="✎ Sửa", width=70, height=26, command=self._edit, **theme.SECONDARY).pack(side="left")
        notes = []
        if not self.data.get("has_history"):
            notes.append("Bạn chưa nghe nhiều nên gợi ý còn dựa vào thể loại đã chọn và độ phổ biến.")
        if self.data.get("top_categories"):
            notes.append("Bạn hay nghe: " + ", ".join(t["name"] for t in self.data["top_categories"]) + ".")
        if notes:
            ctk.CTkLabel(self.summary, text=" ".join(notes), anchor="w", justify="left", wraplength=860,
                         text_color=theme.TEXT_2).pack(anchor="w", pady=(4, 0))

    def _edit(self) -> None:
        self.picked = list(self.data.get("favorite_categories", []))
        self.editing = True
        self._show_summary()

    def _show_picker(self) -> None:
        for child in self.prefs.winfo_children():
            child.destroy()
        self.prefs.grid()
        onboarded = bool(self.data.get("onboarded"))
        ctk.CTkLabel(self.prefs, text="Thể loại yêu thích của bạn" if onboarded else "Bạn thích thể loại nào?",
                     anchor="w", font=theme.font(15, "bold")).grid(row=0, column=0, columnspan=5, padx=16, pady=(12, 0), sticky="w")
        ctk.CTkLabel(self.prefs, text="Chọn vài thể loại để mình gợi ý đúng gu. Bạn đổi lại bất cứ lúc nào.", anchor="w",
                     text_color=theme.MUTED).grid(row=1, column=0, columnspan=5, padx=16, sticky="w")
        grid = ctk.CTkFrame(self.prefs, fg_color="transparent")
        grid.grid(row=2, column=0, columnspan=5, padx=12, pady=8, sticky="w")
        for index, category in enumerate(self.ctx.app.categories):
            on = category["slug"] in self.picked
            ctk.CTkButton(
                grid, text=category["name"], height=28, corner_radius=14, width=118, font=theme.font(12, "bold" if on else "normal"),
                command=lambda s=category["slug"]: self._toggle(s),
                **({"fg_color": theme.ACCENT_SOFT, "hover_color": theme.ACCENT_SOFT, "text_color": theme.ACCENT,
                    "border_width": 1, "border_color": theme.ACCENT} if on else
                   {**theme.SECONDARY, "border_width": 1, "border_color": theme.BORDER_STRONG}),
            ).grid(row=index // 5, column=index % 5, padx=3, pady=3)
        buttons = ctk.CTkFrame(self.prefs, fg_color="transparent")
        buttons.grid(row=3, column=0, columnspan=5, padx=16, pady=(0, 12), sticky="e")
        if onboarded:
            ctk.CTkButton(buttons, text="Hủy", width=80, command=self._cancel_edit, **theme.SECONDARY).pack(side="left", padx=6)
        else:
            ctk.CTkButton(buttons, text="Bỏ qua", width=80, command=lambda: self._save(skip=True), **theme.SECONDARY).pack(side="left", padx=6)
        ctk.CTkButton(buttons, text="Lưu", width=80, command=lambda: self._save(skip=False),
                      state="normal" if self.picked else "disabled").pack(side="left")

    def _toggle(self, slug: str) -> None:
        self.picked = toggle_slug(self.picked, slug)
        self._show_picker()

    def _cancel_edit(self) -> None:
        self.editing = False
        self._show_summary()

    def _save(self, skip: bool) -> None:
        chosen = [] if skip else list(self.picked)

        def done(data: dict[str, Any]) -> None:
            self.editing = False
            self.ctx.app.toast("Đã bỏ qua. Gợi ý sẽ dựa trên lịch sử nghe của bạn." if skip else "Đã lưu thể loại yêu thích.")
            self._loaded(data)

        self.ctx.ui.run_in_thread(lambda: self.ctx.api.save_preferences(chosen), done,
                                  lambda exc: self.ctx.app.show_error(error_text(exc)))

    # -- the list ----------------------------------------------------------------------------------------------------

    def _clear(self) -> None:
        for child in self.list.winfo_children():
            child.destroy()

    def _message(self, text: str, error: bool = False) -> None:
        self._clear()
        ctk.CTkLabel(self.list, text=text, text_color=theme.DANGER if error else theme.TEXT_2, wraplength=700).grid(
            row=0, column=0, columnspan=2, pady=40)
        if error:
            ctk.CTkButton(self.list, text="Thử lại", width=100, command=self.refresh).grid(row=1, column=0, columnspan=2)

    def _show_books(self) -> None:
        if not self.books:
            filtered = self.mood is not None or self._minutes() is not None
            return self._message("Chưa có sách phù hợp. Thử đổi tâm trạng hoặc thời lượng." if filtered else
                                 "Chưa có sách phù hợp. Bạn đã có tất cả sách hệ thống trên kệ, hoặc quản trị viên chưa đăng thêm sách.")
        self._clear()
        for index, book in enumerate(self.books):
            book_card(self.list, self.ctx, index, book, on_listen=lambda b: self._add(b, listen=True), on_add=self._add)

    def _add(self, book: dict[str, Any], listen: bool = False) -> None:
        def done(_result: Any) -> None:
            if listen:
                self.ctx.app.open_in_reader(book["id"], book["title"])
            else:
                self.ctx.app.toast(f'Đã thêm "{book["title"]}" vào kệ.')
            self.refresh()

        self.ctx.ui.run_in_thread(lambda: self.ctx.api.add_to_shelf(book["id"]), done,
                                  lambda exc: self.ctx.app.show_error(error_text(exc)))
