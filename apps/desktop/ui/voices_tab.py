"""S04 – Kho Giọng Đọc: system voices and the user's own clones (preview, default, rename, delete, clone)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

from ui import theme
from ui.common import AppContext, error_text
from ui.dialogs import CloneVoiceDialog, RenameVoiceDialog
from ui.viewmodels import clone_quota, split_voices

_SYSTEM, _MINE = "Giọng hệ thống", "Giọng của tôi"


class VoicesTab(ctk.CTkFrame):
    def __init__(self, master: tk.Misc, ctx: AppContext):
        super().__init__(master, fg_color="transparent")
        self.ctx = ctx
        self.data: dict[str, Any] = {}
        self.shown: list[dict[str, Any]] = []
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(titles, text="Kho Giọng Đọc", anchor="w", font=theme.font(26, "bold")).pack(anchor="w")
        ctk.CTkLabel(titles, text="Nghe thử, chọn giọng mặc định và tạo giọng riêng của bạn.", anchor="w",
                     text_color=theme.MUTED).pack(anchor="w")
        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.grid(row=0, column=1, sticky="e")
        self.quota_label = ctk.CTkLabel(controls, text="", text_color=theme.MUTED)
        self.quota_label.pack(side="left", padx=(0, 10))
        self.add_btn = ctk.CTkButton(controls, text="+ Thêm giọng mới", command=self._open_clone, state="disabled")
        self.add_btn.pack(side="left")

        self.notice = ctk.CTkLabel(self, text="", anchor="w", justify="left", text_color=theme.WARNING, wraplength=860)
        self.notice.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self.group = ctk.CTkSegmentedButton(self, values=[_SYSTEM, _MINE], command=lambda _v: self._render())
        self.group.set(_SYSTEM)
        self.group.grid(row=2, column=0, sticky="w", pady=(0, 8))
        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list.grid(row=3, column=0, sticky="nsew")
        self.list.columnconfigure(0, weight=1)

    # -- data ---------------------------------------------------------------------------------------------

    def refresh(self) -> None:
        self.ctx.ui.run_in_thread(self.ctx.api.list_voices, self._loaded, self._failed)

    def _failed(self, exc: Exception) -> None:
        self.notice.configure(text=error_text(exc), text_color=theme.DANGER)

    def _loaded(self, data: dict[str, Any]) -> None:
        self.data = data
        self.ctx.app.set_voices(data)  # the reader's dropdown shows the same voices
        self._render()

    # -- drawing --------------------------------------------------------------------------------------------

    def _render(self) -> None:
        system, mine = split_voices(self.data.get("voices", []))
        used, maximum, full = clone_quota(self.data)
        self.quota_label.configure(text=f"{used} giọng riêng" if maximum is None else f"{used}/{maximum} giọng riêng")
        supports = bool(self.data.get("supports_cloning"))
        self.add_btn.configure(state="normal" if supports and not full else "disabled")
        notes = [self.data.get("warning") or ""]
        if self.data and not supports:
            notes.append("Nhà cung cấp hiện tại không hỗ trợ tạo giọng.")
        elif full:
            notes.append(f"Bạn đã dùng hết {maximum} giọng riêng. Hãy xóa một giọng để tạo giọng mới.")
        self.notice.configure(text=" ".join(n for n in notes if n), text_color=theme.WARNING)

        mine_tab = self.group.get() == _MINE
        self.shown = mine if mine_tab else system
        for child in self.list.winfo_children():
            child.destroy()
        if not self.shown:
            ctk.CTkLabel(self.list, text="Bạn chưa có giọng riêng nào." if mine_tab else "Chưa có giọng nào.",
                         text_color=theme.MUTED).grid(row=0, column=0, pady=30)
        default = self.ctx.app.settings.get("default_voice")
        for row, voice in enumerate(self.shown):
            self._voice_row(row, voice, is_default=voice["voice_id"] == default)

    def _voice_row(self, row: int, voice: dict[str, Any], is_default: bool) -> None:
        card = ctk.CTkFrame(self.list, fg_color=theme.ACCENT_SOFT if is_default else theme.SURFACE, corner_radius=10,
                            border_width=1, border_color=theme.ACCENT if is_default else theme.BORDER)
        card.grid(row=row, column=0, sticky="ew", pady=4)
        card.columnconfigure(0, weight=1)
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.grid(row=0, column=0, sticky="w", padx=14, pady=10)
        ctk.CTkLabel(info, text=voice.get("display_name") or voice["voice_id"], anchor="w",
                     font=theme.font(14, "bold")).pack(anchor="w")
        gender = {"female": "Nữ", "male": "Nam"}.get(str(voice.get("gender") or ""), "")
        detail = " · ".join(p for p in (gender, str(voice.get("language") or "").upper(), voice.get("style") or "") if p)
        tags = [t for t, on in (("✓ Mặc định", is_default),
                                ("Giọng chung", voice.get("is_custom") and voice.get("is_public")),
                                ("Riêng tư", voice.get("is_custom") and voice.get("is_mine") and not voice.get("is_public"))) if on]
        ctk.CTkLabel(info, text="   ".join(p for p in (detail, *tags) if p), anchor="w", text_color=theme.MUTED).pack(anchor="w")
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=0, column=1, padx=10)
        ctk.CTkButton(actions, text="▶ Nghe thử", width=96, **theme.SECONDARY,
                      command=lambda v=voice: self._preview(v)).pack(side="left", padx=2)
        ctk.CTkButton(actions, text="★ Đặt mặc định", width=118, **theme.SECONDARY,
                      state="disabled" if is_default else "normal",
                      command=lambda v=voice: self._make_default(v)).pack(side="left", padx=2)
        can_edit = voice.get("is_custom") and (voice.get("is_mine") or self.ctx.user.get("role") == "admin")
        if can_edit:
            ctk.CTkButton(actions, text="✎", width=36, **theme.GHOST,
                          command=lambda v=voice: RenameVoiceDialog(self, self.ctx, v, self.refresh)).pack(side="left", padx=2)
            ctk.CTkButton(actions, text="🗑", width=36, **theme.DANGER_BUTTON,
                          command=lambda v=voice: self._delete(v)).pack(side="left", padx=2)

    # -- actions ----------------------------------------------------------------------------------------------

    def _preview(self, voice: dict[str, Any]) -> None:
        self.notice.configure(text="Đang tải giọng nghe thử…", text_color=theme.WARNING)

        def work() -> None:
            data, ext = self.ctx.api.preview_voice(voice["voice_id"])
            self.ctx.output.play(data, ext)

        self.ctx.ui.run_in_thread(work, lambda _r: self.notice.configure(text=""), self._failed)

    def _make_default(self, voice: dict[str, Any]) -> None:
        settings = {k: self.ctx.app.settings[k] for k in ("prefetch_count", "default_speed", "daily_char_limit")}
        settings["default_voice"] = voice["voice_id"]

        def done(saved: dict[str, Any]) -> None:
            self.ctx.app.settings = saved
            self.ctx.app.select_voice(voice["voice_id"])
            self.ctx.app.toast(f'Đã đặt "{voice["display_name"]}" làm giọng mặc định')
            self._render()

        self.ctx.ui.run_in_thread(lambda: self.ctx.api.update_settings(settings), done, self._failed)

    def _delete(self, voice: dict[str, Any]) -> None:
        if not messagebox.askyesno("Xóa giọng", f'Xóa giọng "{voice["display_name"]}"? Việc này không thể hoàn tác.', parent=self):
            return
        self.ctx.ui.run_in_thread(lambda: self.ctx.api.delete_voice(voice["voice_id"]), lambda _r: self.refresh(), self._failed)

    def _open_clone(self) -> None:
        low, high = self.data.get("clone_sample_seconds", (5, 15))
        CloneVoiceDialog(self, self.ctx, on_created=self._cloned, sample_seconds=(low, high))

    def _cloned(self, voice: dict[str, Any]) -> None:
        self.group.set(_MINE)
        self.refresh()
        self.ctx.app.toast(f'Đã tạo giọng "{voice["display_name"]}"')
