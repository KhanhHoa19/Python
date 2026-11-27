"""S11 – Quản trị (admin only): system books, categories, system voices, accounts."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

from ui import theme
from ui.common import AppContext, error_text
from ui.dialogs import (
    AddAmbientDialog,
    CategoryDialog,
    EditBookDialog,
    RenameVoiceDialog,
    UploadDialog,
)
from ui.viewmodels import format_datetime, sort_system_books

_BOOKS, _CATEGORIES, _VOICES, _AMBIENT, _USERS = "Sách hệ thống", "Thể loại", "Giọng hệ thống", "Âm thanh nền", "Người dùng"


class AdminTab(ctk.CTkFrame):
    def __init__(self, master: tk.Misc, ctx: AppContext):
        super().__init__(master, fg_color="transparent")
        self.ctx = ctx
        self.default_voice = ""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        titles = ctk.CTkFrame(self, fg_color="transparent")
        titles.grid(row=0, column=0, sticky="w", pady=(0, 12))
        ctk.CTkLabel(titles, text="Quản Trị", anchor="w", font=theme.font(26, "bold")).pack(anchor="w")
        ctk.CTkLabel(titles, text="Quản lý nội dung dùng chung cho mọi người.", anchor="w",
                     text_color=theme.MUTED).pack(anchor="w")
        self.section = ctk.CTkSegmentedButton(self, values=[_BOOKS, _CATEGORIES, _VOICES, _AMBIENT, _USERS], command=lambda _v: self.refresh())
        self.section.set(_BOOKS)
        self.section.grid(row=1, column=0, sticky="w")
        self.hint = ctk.CTkLabel(self, text="", anchor="w", justify="left", text_color=theme.MUTED, wraplength=860)
        self.hint.grid(row=2, column=0, sticky="ew", pady=(8, 6))
        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list.grid(row=3, column=0, sticky="nsew")
        self.list.columnconfigure(0, weight=1)

    # -- loading ------------------------------------------------------------------------------------------------

    def refresh(self) -> None:
        loaders: dict[str, tuple[Callable[[], Any], Callable[[Any], None], str]] = {
            _BOOKS: (self.ctx.api.admin_books, self._show_books,
                     "Sách công khai hiện ở Khám Phá của mọi người. Bạn chỉ công khai được sách do chính bạn tải lên."),
            _CATEGORIES: (self.ctx.api.admin_categories, self._show_categories,
                          "Thể loại hiện ở thanh bên của mọi người. Xóa một thể loại không xóa sách trong đó."),
            _VOICES: (self.ctx.api.admin_voices, self._show_voices,
                      "Giọng công khai ai cũng nghe và dùng được. Giọng mặc định hệ thống áp dụng cho người chưa tự chọn giọng."),
            _AMBIENT: (self.ctx.api.list_ambient, self._show_ambient,
                       "Mọi người chọn âm thanh nền của mình từ danh sách này (nút “Nhạc nền” ở Phòng Đọc). Chỉ thêm nhạc không dính bản quyền."),
            _USERS: (self.ctx.api.admin_users, self._show_users,
                     "Chỉ xem. Quản trị viên không đọc được sách hay ghi chú riêng của người dùng."),
        }
        name = self.section.get()
        load, show, hint = loaders[name]
        self.hint.configure(text=hint, text_color=theme.MUTED)
        self.ctx.ui.run_in_thread(load, lambda data: self.section.get() == name and show(data), self._failed)

    def _failed(self, exc: Exception) -> None:
        self.hint.configure(text=error_text(exc), text_color=theme.DANGER)

    def _act(self, work: Callable[[], Any], toast: str) -> None:
        """Run an admin change, then reload the section."""
        self.ctx.ui.run_in_thread(work, lambda _r: self._changed(toast), self._failed)

    def _changed(self, toast: str) -> None:
        self.ctx.app.toast(toast)
        self.refresh()
        self.ctx.app.reload_shared()

    # -- drawing helpers --------------------------------------------------------------------------------------------

    def _clear(self) -> None:
        for child in self.list.winfo_children():
            child.destroy()

    def _card(self, row: int) -> ctk.CTkFrame:
        card = ctk.CTkFrame(self.list, fg_color=theme.SURFACE, corner_radius=10, border_width=1, border_color=theme.BORDER)
        card.grid(row=row, column=0, sticky="ew", pady=4)
        card.columnconfigure(0, weight=1)
        return card

    def _info(self, card: ctk.CTkFrame, title: str, detail: str) -> None:
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.grid(row=0, column=0, sticky="w", padx=14, pady=10)
        ctk.CTkLabel(info, text=title, anchor="w", font=theme.font(14, "bold")).pack(anchor="w")
        ctk.CTkLabel(info, text=detail, anchor="w", text_color=theme.MUTED).pack(anchor="w")

    def _actions(self, card: ctk.CTkFrame) -> ctk.CTkFrame:
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=0, column=1, padx=10)
        return actions

    def _empty(self, text: str) -> None:
        ctk.CTkLabel(self.list, text=text, text_color=theme.MUTED).grid(row=0, column=0, pady=30)

    # -- sách hệ thống -------------------------------------------------------------------------------------------------

    def _show_books(self, books: list[dict[str, Any]]) -> None:
        self._clear()
        add = ctk.CTkButton(self.list, text="+ Thêm sách hệ thống", width=170, command=self._add_book)
        add.grid(row=0, column=0, sticky="e", pady=(0, 4))
        if not books:
            ctk.CTkLabel(self.list, text="Chưa có sách hệ thống nào. Dùng “Thêm sách hệ thống” để đăng cuốn đầu tiên.",
                         text_color=theme.MUTED).grid(row=1, column=0, pady=30)
        for row, book in enumerate(sort_system_books(books), start=1):
            card = self._card(row)
            category = f" · {book['category']['name']}" if book.get("category") else ""
            state = f"Công khai · {book['shelf_count']} kệ" if book["is_public"] else "Riêng tư"
            self._info(card, book["title"], f"{book.get('author') or 'Không rõ tác giả'} · {book['total_chapters']} chương{category}   {state}")
            actions = self._actions(card)
            if book["is_public"]:
                ctk.CTkButton(actions, text="Gỡ công khai", width=110, **theme.SECONDARY,
                              command=lambda b=book: self._unpublish_book(b)).pack(side="left", padx=2)
            else:
                ctk.CTkButton(actions, text="Công khai", width=100, state="normal" if book["is_mine"] else "disabled",
                              command=lambda b=book: self._act(lambda: self.ctx.api.set_book_public(b["id"], True),
                                                               f'Đã công khai "{b["title"]}"')).pack(side="left", padx=2)
            ctk.CTkButton(actions, text="✎", width=36, **theme.GHOST, command=lambda b=book: self._edit_book(b)).pack(side="left", padx=2)
            ctk.CTkButton(actions, text="🗑", width=36, **theme.DANGER_BUTTON,
                          command=lambda b=book: self._delete_book(b)).pack(side="left", padx=2)

    def _add_book(self) -> None:
        UploadDialog(self, self.ctx, on_done=lambda r: self._changed(f'Đã thêm "{r.get("title", "sách")}"'),
                     default_public=True)

    def _edit_book(self, book: dict[str, Any]) -> None:
        full = {"id": book["id"], "title": book["title"], "author": book.get("author"), "category": book.get("category"),
                "cover_url": book.get("cover_url")}
        EditBookDialog(self, self.ctx, full, on_saved=lambda saved: self._changed(f'Đã lưu "{saved["title"]}"'))

    def _delete_book(self, book: dict[str, Any]) -> None:
        extra = (f" {book['shelf_count']} người đang giữ sách này sẽ mất sách cùng tiến độ nghe và trích dẫn của họ."
                 if book["shelf_count"] else "")
        if messagebox.askyesno("Xóa sách", f'Xóa hẳn "{book["title"]}"?{extra} Việc này không thể hoàn tác.', parent=self):
            self._act(lambda: self.ctx.api.delete_book(book["id"]), f'Đã xóa "{book["title"]}"')

    def _unpublish_book(self, book: dict[str, Any]) -> None:
        extra = f" {book['shelf_count']} người đang để sách này trên kệ sẽ không còn thấy nó nữa." if book["shelf_count"] else ""
        if messagebox.askyesno("Gỡ công khai", f'Gỡ "{book["title"]}" khỏi Khám Phá?{extra}', parent=self):
            self._act(lambda: self.ctx.api.set_book_public(book["id"], False), f'Đã gỡ "{book["title"]}" khỏi Khám phá')

    # -- thể loại ----------------------------------------------------------------------------------------------------------

    def _show_categories(self, categories: list[dict[str, Any]]) -> None:
        self._clear()
        add = ctk.CTkButton(self.list, text="+ Thêm thể loại", width=140, command=lambda: self._edit_category(None))
        add.grid(row=0, column=0, sticky="e", pady=(0, 4))
        for row, category in enumerate(categories, start=1):
            card = self._card(row)
            self._info(card, f"●  {category['name']}", f"{category['book_count']} sách · {category['slug']}")
            actions = self._actions(card)
            ctk.CTkButton(actions, text="✎", width=36, **theme.GHOST, command=lambda c=category: self._edit_category(c)).pack(side="left", padx=2)
            ctk.CTkButton(actions, text="🗑", width=36, **theme.DANGER_BUTTON, state="disabled" if category["slug"] == "khac" else "normal",
                          command=lambda c=category: self._delete_category(c)).pack(side="left", padx=2)

    def _edit_category(self, category: dict[str, Any] | None) -> None:
        CategoryDialog(self, self.ctx, category, lambda: (self.refresh(), self.ctx.app.reload_shared()))

    def _delete_category(self, category: dict[str, Any]) -> None:
        if messagebox.askyesno("Xóa thể loại", f'Xóa thể loại "{category["name"]}"? {category["book_count"]} sách trong đó sẽ trở thành chưa phân loại.', parent=self):
            self._act(lambda: self.ctx.api.delete_category(category["id"]), f'Đã xóa thể loại "{category["name"]}"')

    # -- giọng hệ thống -------------------------------------------------------------------------------------------------------

    def _show_voices(self, data: dict[str, Any]) -> None:
        self._clear()
        voices, default = data["voices"], data["default_voice"]
        if not voices:
            return self._empty("Chưa có giọng nào để chia sẻ. Tạo một giọng ở Kho Giọng Đọc trước.")
        for row, voice in enumerate(voices):
            card = self._card(row)
            tags = ["Công khai" if voice["is_public"] else "Riêng tư"] + (["✓ Mặc định hệ thống"] if voice["voice_id"] == default else [])
            self._info(card, voice["display_name"], "   ".join(tags))
            actions = self._actions(card)
            vid, name = voice["voice_id"], voice["display_name"]
            if voice["is_public"]:
                ctk.CTkButton(actions, text="★ Đặt mặc định", width=118, **theme.SECONDARY, state="disabled" if vid == default else "normal",
                              command=lambda v=vid, n=name: self._act(lambda: self.ctx.api.set_default_voice(v), f'Đã đặt "{n}" làm giọng mặc định hệ thống')).pack(side="left", padx=2)
                ctk.CTkButton(actions, text="Gỡ công khai", width=110, **theme.SECONDARY, state="disabled" if vid == default else "normal",
                              command=lambda v=vid, n=name: self._act(lambda: self.ctx.api.set_voice_public(v, False), f'Đã gỡ "{n}"')).pack(side="left", padx=2)
            else:
                ctk.CTkButton(actions, text="Công khai", width=100, state="normal" if voice["is_mine"] else "disabled",
                              command=lambda v=vid, n=name: self._act(lambda: self.ctx.api.set_voice_public(v, True), f'Đã công khai "{n}"')).pack()

    # -- âm thanh nền ------------------------------------------------------------------------------------------------------------

    def _show_ambient(self, tracks: list[dict[str, Any]]) -> None:
        self._clear()
        ctk.CTkButton(self.list, text="+ Thêm âm thanh", width=150,
                      command=lambda: AddAmbientDialog(self, self.ctx, lambda: self._changed("Đã thêm âm thanh nền"))
                      ).grid(row=0, column=0, sticky="e", pady=(0, 4))
        if not tracks:
            ctk.CTkLabel(self.list, text="Chưa có âm thanh nền nào.", text_color=theme.MUTED).grid(row=1, column=0, pady=30)
        for row, track in enumerate(tracks, start=1):
            card = self._card(row)
            self._info(card, track["name"], f"{track['size_bytes'] / (1024 * 1024):.1f} MB")
            actions = self._actions(card)
            ctk.CTkButton(actions, text="▶ Nghe thử", width=96, **theme.SECONDARY,
                          command=lambda t=track: self._preview_ambient(t)).pack(side="left", padx=2)
            ctk.CTkButton(actions, text="✎", width=36, **theme.GHOST, command=lambda t=track: self._rename_ambient(t)).pack(side="left", padx=2)
            ctk.CTkButton(actions, text="🗑", width=36, **theme.DANGER_BUTTON,
                          command=lambda t=track: self._delete_ambient(t)).pack(side="left", padx=2)

    def _preview_ambient(self, track: dict[str, Any]) -> None:
        def work() -> None:
            data, ext = self.ctx.api.fetch_ambient(track["id"])
            self.ctx.output.play(data, ext)

        self.ctx.ui.run_in_thread(work, lambda _r: None, self._failed)

    def _rename_ambient(self, track: dict[str, Any]) -> None:
        RenameVoiceDialog(self, self.ctx, {"voice_id": track["id"], "display_name": track["name"]}, self.refresh,
                          rename=lambda name: self.ctx.api.rename_ambient(track["id"], name), title="Đổi tên âm thanh")

    def _delete_ambient(self, track: dict[str, Any]) -> None:
        if messagebox.askyesno("Xóa âm thanh nền", f'Xóa "{track["name"]}"? Ai đang dùng bản này sẽ không còn nghe nhạc nền cho tới khi chọn bản khác.', parent=self):
            self._act(lambda: self.ctx.api.delete_ambient(track["id"]), f'Đã xóa "{track["name"]}"')

    # -- người dùng ------------------------------------------------------------------------------------------------------------

    def _show_users(self, users: list[dict[str, Any]]) -> None:
        self._clear()
        for row, user in enumerate(users):
            card = self._card(row)
            role = "ADMIN" if user["role"] == "admin" else "MEMBER"
            self._info(card, f"{user['full_name']} ({user['username']})",
                       f"{role} · tạo {format_datetime(user['created_at'])} · {user['book_count']} sách · {user['voice_count']} giọng")
