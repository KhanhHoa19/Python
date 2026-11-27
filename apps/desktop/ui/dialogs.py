"""Modal dialogs: S02 upload, S04 clone/rename voice, S11 category, S05 connection & settings, S06 note, S07 export."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog
from typing import Any, ClassVar

import customtkinter as ctk

import config
from player.chapters import describe_chapter
from player.sleep_timer import CUSTOM_MINUTES_MAX, MINUTE_PRESETS, parse_custom_minutes
from ui import theme
from ui.common import AppContext, ModalDialog, error_text
from ui.images import CoverView
from ui.viewmodels import (
    CATEGORY_ICONS,
    EMOTIONS,
    category_problem,
    check_book_title,
    describe_voice,
    format_number,
    usage_ratio,
)

_ERROR_COLOR = theme.DANGER
_OK_COLOR = theme.SUCCESS
_WARN_COLOR = theme.WARNING


def _label(master: tk.Misc, text: str, **kwargs: Any) -> ctk.CTkLabel:
    return ctk.CTkLabel(master, text=text, anchor="w", justify="left", **kwargs)


# ============================================================ S02 – Thêm tài liệu


class UploadDialog(ModalDialog):
    def __init__(self, master: tk.Misc, ctx: AppContext, on_done: Callable[[dict[str, Any]], None],
                 default_public: bool = False):
        super().__init__(master, "Thêm tài liệu", 520, 560)
        self.ctx, self.on_done = ctx, on_done
        self.path: Path | None = None
        self.cover: Path | None = None
        self.columnconfigure(0, weight=1)

        _label(self, "Hỗ trợ: PDF (có lớp chữ), DOCX, TXT, MD · Tối đa 10 MB").grid(
            row=0, column=0, padx=20, pady=(20, 4), sticky="w")
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=1, column=0, padx=20, sticky="ew")
        row.columnconfigure(0, weight=1)
        self.file_label = _label(row, "Chưa chọn file")
        self.file_label.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(row, text="Chọn file…", width=110, command=self._choose).grid(row=0, column=1)

        _label(self, "Tên tài liệu").grid(row=2, column=0, padx=20, pady=(14, 0), sticky="w")
        self.title_entry = ctk.CTkEntry(self)
        self.title_entry.grid(row=3, column=0, padx=20, sticky="ew")
        _label(self, "Tác giả (không bắt buộc)").grid(row=4, column=0, padx=20, pady=(10, 0), sticky="w")
        self.author_entry = ctk.CTkEntry(self)
        self.author_entry.grid(row=5, column=0, padx=20, sticky="ew")

        _label(self, "Thể loại").grid(row=6, column=0, padx=20, pady=(10, 0), sticky="w")
        self.categories = ctx.app.categories
        self.category_box = ctk.CTkComboBox(self, values=["Khác (mặc định)"] + [c["name"] for c in self.categories], state="readonly")
        self.category_box.set("Khác (mặc định)")
        self.category_box.grid(row=7, column=0, padx=20, sticky="ew")
        cover_row = ctk.CTkFrame(self, fg_color="transparent")
        cover_row.grid(row=8, column=0, padx=20, pady=(10, 0), sticky="ew")
        cover_row.columnconfigure(0, weight=1)
        self.cover_label = _label(cover_row, "Ảnh bìa: tự tạo (PDF dùng trang đầu)", text_color=theme.MUTED)
        self.cover_label.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(cover_row, text="Chọn ảnh…", width=110, command=self._choose_cover, **theme.SECONDARY).grid(row=0, column=1)
        self.public_var = tk.BooleanVar(value=default_public and ctx.user.get("role") == "admin")
        if ctx.user.get("role") == "admin":
            ctk.CTkCheckBox(self, text="Công khai cho mọi người (sách hệ thống, hiện trong Khám phá)",
                            variable=self.public_var).grid(row=9, column=0, padx=20, pady=(12, 0), sticky="w")

        self.status = _label(self, "", text_color=_ERROR_COLOR, wraplength=470)
        self.status.grid(row=10, column=0, padx=20, pady=(10, 0), sticky="w")
        self.progress = ctk.CTkProgressBar(self, mode="indeterminate")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=12, column=0, padx=20, pady=16, sticky="e")
        self.cancel_btn = ctk.CTkButton(buttons, text="Hủy", width=90, **theme.SECONDARY, command=self.close)
        self.cancel_btn.pack(side="left", padx=(0, 8))
        self.upload_btn = ctk.CTkButton(buttons, text="Tải lên", width=110, state="disabled", command=self._upload)
        self.upload_btn.pack(side="left")

    def _choose(self) -> None:
        chosen = filedialog.askopenfilename(
            parent=self, title="Chọn tài liệu",
            filetypes=[("Tài liệu", "*.pdf *.docx *.txt *.md"), ("Tất cả", "*.*")],
        )
        if not chosen:
            return
        self.path = Path(chosen)
        self.file_label.configure(text=self.path.name)
        if not self.title_entry.get().strip():
            self.title_entry.insert(0, self.path.stem.replace("_", " ").title())
        self.upload_btn.configure(state="normal")
        self.status.configure(text="")

    def _choose_cover(self) -> None:
        chosen = filedialog.askopenfilename(parent=self, title="Chọn ảnh bìa",
                                            filetypes=[("Ảnh JPEG/PNG", "*.jpg *.jpeg *.png"), ("Tất cả", "*.*")])
        if not chosen:
            return
        picked = Path(chosen)
        if picked.stat().st_size > 2 * 1024 * 1024:
            self.status.configure(text="Ảnh bìa tối đa 2 MB.", text_color=_ERROR_COLOR)
            return
        self.cover = picked
        self.cover_label.configure(text=f"Ảnh bìa: {picked.name}", text_color=theme.TEXT)

    def _category_id(self) -> int | None:
        """The chosen category's id, or None for the default ("Khác")."""
        return next((c["id"] for c in self.categories if c["name"] == self.category_box.get()), None)

    def _upload(self) -> None:
        if not self.path:
            return
        if self.path.stat().st_size > 10 * 1024 * 1024:
            self.status.configure(text="File vượt quá 10 MB.")
            return
        self.upload_btn.configure(state="disabled")
        self.status.configure(text="Đang tải lên và tách câu…", text_color=theme.TEXT_2)
        self.progress.grid(row=11, column=0, padx=20, sticky="ew")
        self.progress.start()
        path, title, author = self.path, self.title_entry.get().strip(), self.author_entry.get().strip()
        category_id, cover, is_public = self._category_id(), self.cover, bool(self.public_var.get())
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.ingest_book(path, title, author, category_id, cover, is_public),
            self.guard(self._done), self.guard(self._failed),
        )

    def _done(self, result: dict[str, Any]) -> None:
        self.on_done(result)
        self.close()

    def _failed(self, exc: Exception) -> None:
        self.progress.stop()
        self.progress.grid_forget()
        message = error_text(exc)
        if "empty" in message.lower() and "pdf" in message.lower():
            message = "Không đọc được chữ. Có thể đây là PDF scan (chưa hỗ trợ OCR)."
        self.status.configure(text=message, text_color=_ERROR_COLOR)
        self.upload_btn.configure(state="normal")


# ============================================================ S04 – Thêm giọng (Kho Giọng Đọc) · S11 – Quản trị


class RenameVoiceDialog(ModalDialog):
    """Change the name of a cloned voice."""

    def __init__(self, master: tk.Misc, ctx: AppContext, voice: dict[str, Any], on_done: Callable[[], None],
                 rename: Callable[[str], Any] | None = None, title: str = "Đổi tên giọng"):
        super().__init__(master, title, 440, 220)
        self.ctx, self.voice, self.on_done = ctx, voice, on_done
        self._rename = rename or (lambda name: ctx.api.rename_voice(voice["voice_id"], name))
        self.columnconfigure(0, weight=1)
        _label(self, "Tên giọng").grid(row=0, column=0, padx=20, pady=(20, 0), sticky="w")
        self.name_entry = ctk.CTkEntry(self)
        self.name_entry.insert(0, voice["display_name"])
        self.name_entry.grid(row=1, column=0, padx=20, sticky="ew")
        self.status = _label(self, "", text_color=_ERROR_COLOR, wraplength=400)
        self.status.grid(row=2, column=0, padx=20, pady=(8, 0), sticky="w")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=3, column=0, padx=20, pady=16, sticky="e")
        ctk.CTkButton(buttons, text="Hủy", width=90, **theme.SECONDARY, command=self.close).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="Lưu", width=90, command=self._save).pack(side="left")

    def _save(self) -> None:
        name = self.name_entry.get().strip()
        if not name:
            self.status.configure(text="Hãy nhập tên giọng.")
            return
        self.ctx.ui.run_in_thread(
            lambda: self._rename(name),
            self.guard(self._done), self.guard(lambda exc: self.status.configure(text=error_text(exc))))

    def _done(self, _result: dict[str, Any]) -> None:
        self.on_done()
        self.close()


class CategoryDialog(ModalDialog):
    """Admin: add or edit a category (name, icon, colour)."""

    def __init__(self, master: tk.Misc, ctx: AppContext, category: dict[str, Any] | None, on_done: Callable[[], None]):
        super().__init__(master, "Sửa thể loại" if category else "Thêm thể loại", 460, 330)
        self.ctx, self.category, self.on_done = ctx, category, on_done
        self.columnconfigure(0, weight=1)
        _label(self, "Tên thể loại").grid(row=0, column=0, padx=20, pady=(20, 0), sticky="w")
        self.name_entry = ctk.CTkEntry(self)
        self.name_entry.insert(0, category["name"] if category else "")
        self.name_entry.grid(row=1, column=0, padx=20, sticky="ew")
        opts = ctk.CTkFrame(self, fg_color="transparent")
        opts.grid(row=2, column=0, padx=20, pady=12, sticky="w")
        _label(opts, "Biểu tượng").grid(row=0, column=0, padx=(0, 6))
        self.icon_labels = {value: label for value, label in CATEGORY_ICONS}
        self.icon = ctk.CTkComboBox(opts, values=list(self.icon_labels.values()), width=130, state="readonly")
        self.icon.set(self.icon_labels.get(category["icon"] if category else "book-open", "Sách mở"))
        self.icon.grid(row=0, column=1, padx=(0, 20))
        _label(opts, "Màu (#rrggbb)").grid(row=0, column=2, padx=(0, 6))
        self.color = ctk.CTkEntry(opts, width=90)
        self.color.insert(0, category["color"] if category else "#8a6d3b")
        self.color.grid(row=0, column=3)
        self.status = _label(self, "", text_color=_ERROR_COLOR, wraplength=420)
        self.status.grid(row=3, column=0, padx=20, sticky="w")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=4, column=0, padx=20, pady=16, sticky="e")
        ctk.CTkButton(buttons, text="Hủy", width=90, **theme.SECONDARY, command=self.close).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="Lưu", width=90, command=self._save).pack(side="left")

    def _save(self) -> None:
        name, color = self.name_entry.get().strip(), self.color.get().strip()
        problem = category_problem(name, color)
        if problem:
            self.status.configure(text=problem)
            return
        icon = next((v for v, label in self.icon_labels.items() if label == self.icon.get()), "book-open")
        api, category = self.ctx.api, self.category
        work = (lambda: api.update_category(category["id"], name, icon, color)) if category else (
            lambda: api.create_category(name, icon, color))
        self.ctx.ui.run_in_thread(work, self.guard(self._done), self.guard(lambda exc: self.status.configure(text=error_text(exc))))

    def _done(self, _result: dict[str, Any]) -> None:
        self.on_done()
        self.close()


class CloneVoiceDialog(ModalDialog):
    def __init__(self, master: tk.Misc, ctx: AppContext, on_created: Callable[[dict[str, Any]], None],
                 sample_seconds: tuple[float, float] = (5, 15)):
        super().__init__(master, "Thêm giọng mới", 520, 420)
        self.ctx, self.on_created = ctx, on_created
        self.sample: Path | None = None
        self.consent = tk.BooleanVar(value=False)
        self.columnconfigure(0, weight=1)

        _label(self, "Tên giọng").grid(row=0, column=0, padx=20, pady=(20, 0), sticky="w")
        self.name_entry = ctk.CTkEntry(self)
        self.name_entry.grid(row=1, column=0, padx=20, sticky="ew")
        _label(self, f"File mẫu ({sample_seconds[0]:g}–{sample_seconds[1]:g} giây, WAV/MP3)").grid(row=2, column=0, padx=20, pady=(12, 0), sticky="w")
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=3, column=0, padx=20, sticky="ew")
        row.columnconfigure(0, weight=1)
        self.file_label = _label(row, "Chưa chọn file")
        self.file_label.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(row, text="Chọn file…", width=110, command=self._choose).grid(row=0, column=1)

        opts = ctk.CTkFrame(self, fg_color="transparent")
        opts.grid(row=4, column=0, padx=20, pady=12, sticky="w")
        _label(opts, "Ngôn ngữ").grid(row=0, column=0, padx=(0, 6))
        self.language = ctk.CTkComboBox(opts, values=["vi", "en"], width=80, state="readonly")
        self.language.set("vi")
        self.language.grid(row=0, column=1, padx=(0, 20))
        _label(opts, "Giới tính").grid(row=0, column=2, padx=(0, 6))
        self.gender = ctk.CTkComboBox(opts, values=["Nữ", "Nam"], width=80, state="readonly")
        self.gender.set("Nữ")
        self.gender.grid(row=0, column=3)

        ctk.CTkCheckBox(
            self, text="Tôi xác nhận đây là giọng của tôi hoặc tôi được\nchủ giọng đồng ý.",
            variable=self.consent, command=self._refresh,
        ).grid(row=5, column=0, padx=20, sticky="w")
        self.status = _label(self, "", text_color=_ERROR_COLOR, wraplength=470)
        self.status.grid(row=6, column=0, padx=20, pady=(10, 0), sticky="w")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=7, column=0, padx=20, pady=16, sticky="e")
        ctk.CTkButton(buttons, text="Hủy", width=90, **theme.SECONDARY, command=self.close).pack(side="left", padx=(0, 8))
        self.create_btn = ctk.CTkButton(buttons, text="Tạo giọng", width=110, state="disabled", command=self._create)
        self.create_btn.pack(side="left")

    def _choose(self) -> None:
        chosen = filedialog.askopenfilename(
            parent=self, title="Chọn file mẫu", filetypes=[("Audio", "*.wav *.mp3 *.m4a *.ogg")])
        if chosen:
            self.sample = Path(chosen)
            self.file_label.configure(text=self.sample.name)
            self._refresh()

    def _refresh(self) -> None:
        ready = self.sample is not None and self.consent.get()
        self.create_btn.configure(state="normal" if ready else "disabled")

    def _create(self) -> None:
        name = self.name_entry.get().strip()
        if not name or not self.sample or not self.consent.get():
            self.status.configure(text="Hãy nhập tên, chọn file mẫu và tick đồng thuận.")
            return
        self.create_btn.configure(state="disabled")
        self.status.configure(text="Đang tạo giọng… (có thể mất vài chục giây)", text_color=_WARN_COLOR)
        sample, language = self.sample, self.language.get()
        gender = "female" if self.gender.get() == "Nữ" else "male"
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.clone_voice(sample, name, language, gender, consent=True),
            self.guard(self._done), self.guard(self._failed))

    def _done(self, voice: dict[str, Any]) -> None:
        self.on_created(voice)
        self.close()

    def _failed(self, exc: Exception) -> None:
        self.status.configure(text=error_text(exc), text_color=_ERROR_COLOR)
        self._refresh()


# ============================================================ S05 – Kết nối & Cài đặt


class SettingsDialog(ModalDialog):
    CHECKS = ("dns", "port", "latency", "synth")
    CHECK_LABELS: ClassVar[dict[str, str]] = {"dns": "DNS", "port": "Cổng 443", "latency": "Độ trễ mạng", "synth": "Thử đọc 1 câu"}

    def __init__(self, master: tk.Misc, ctx: AppContext):
        super().__init__(master, "Kết nối & Cài đặt", 560, 640)
        self.ctx = ctx
        self.columnconfigure(0, weight=1)

        _label(self, "KẾT NỐI", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=20, pady=(16, 4), sticky="w")
        self.provider = _label(self, "Nhà cung cấp: …")
        self.provider.grid(row=1, column=0, padx=20, sticky="w")
        _label(self, "API Key đặt trong file .env phía backend, không nhập ở đây.",
               text_color=theme.MUTED).grid(row=2, column=0, padx=20, sticky="w")
        self.check_btn = ctk.CTkButton(self, text="Kiểm tra kết nối", command=self._run_checks)
        self.check_btn.grid(row=3, column=0, padx=20, pady=8, sticky="w")
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.grid(row=4, column=0, padx=20, sticky="ew")
        if ctx.user.get("role") != "admin":  # the checks use the shared TTS account: administrators only
            self.check_btn.grid_remove()
            grid.grid_remove()
        grid.columnconfigure(1, weight=1)
        self.rows: dict[str, tuple[ctk.CTkLabel, ctk.CTkLabel]] = {}
        for i, key in enumerate(self.CHECKS):
            icon = _label(grid, "·", width=24)
            icon.grid(row=i, column=0)
            detail = _label(grid, f"{self.CHECK_LABELS[key]}", wraplength=440)
            detail.grid(row=i, column=1, sticky="w")
            self.rows[key] = (icon, detail)

        _label(self, "CÀI ĐẶT ĐỌC", font=ctk.CTkFont(weight="bold")).grid(row=5, column=0, padx=20, pady=(20, 4), sticky="w")
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.grid(row=6, column=0, padx=20, sticky="ew")
        form.columnconfigure(1, weight=1)
        _label(form, "Số câu tải trước").grid(row=0, column=0, pady=4, sticky="w")
        self.prefetch = ctk.CTkComboBox(form, values=["1", "2", "3", "4", "5"], width=90, state="readonly")
        self.prefetch.grid(row=0, column=1, sticky="w", padx=10)
        _label(form, "Tốc độ mặc định").grid(row=1, column=0, pady=4, sticky="w")
        self.speed = ctk.CTkComboBox(form, values=[f"{s}x" for s in config.SPEED_LEVELS], width=90, state="readonly")
        self.speed.grid(row=1, column=1, sticky="w", padx=10)
        _label(form, "Giọng mặc định").grid(row=2, column=0, pady=4, sticky="w")
        self.voice = ctk.CTkComboBox(form, values=[""], width=300, state="readonly")
        self.voice.grid(row=2, column=1, sticky="w", padx=10)
        _label(form, "Giới hạn ký tự/ngày").grid(row=3, column=0, pady=4, sticky="w")
        self.limit = ctk.CTkEntry(form, width=120)
        self.limit.grid(row=3, column=1, sticky="w", padx=10)
        self.limit_locked = ctx.user.get("role") != "admin"  # the limit is shared by everyone: admins only
        _label(form, "(chỉ quản trị viên thay đổi)" if self.limit_locked else "(0 = không giới hạn)",
               text_color=theme.MUTED).grid(row=3, column=1, sticky="e")

        self.usage_label = _label(self, "")
        self.usage_label.grid(row=7, column=0, padx=20, pady=(10, 0), sticky="w")
        self.usage_bar = ctk.CTkProgressBar(self)
        self.usage_bar.grid(row=8, column=0, padx=20, pady=4, sticky="ew")
        self.usage_bar.set(0)

        self.status = _label(self, "", wraplength=500)
        self.status.grid(row=9, column=0, padx=20, pady=(8, 0), sticky="w")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=10, column=0, padx=20, pady=16, sticky="e")
        ctk.CTkButton(buttons, text="Đóng", width=90, **theme.SECONDARY, command=self.close).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="Lưu cài đặt", width=120, command=self._save).pack(side="left")
        self._voice_ids: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        def work() -> tuple[dict[str, Any], dict[str, Any]]:
            return self.ctx.api.get_settings(), self.ctx.api.list_voices()

        self.ctx.ui.run_in_thread(work, self.guard(self._loaded), self.guard(self._failed))

    def _failed(self, exc: Exception) -> None:
        self.status.configure(text=error_text(exc), text_color=_ERROR_COLOR)

    def _loaded(self, result: tuple[dict[str, Any], dict[str, Any]]) -> None:
        settings, voices = result
        self.provider.configure(text=f"Nhà cung cấp: {settings['provider']}")
        self.prefetch.set(str(settings["prefetch_count"]))
        self.speed.set(f"{settings['default_speed']}x")
        self._voice_ids = {describe_voice(v): v["voice_id"] for v in voices["voices"]}
        names = list(self._voice_ids) or [settings["default_voice"]]
        current = next((n for n, vid in self._voice_ids.items() if vid == settings["default_voice"]), None)
        self.voice.configure(values=names)
        self.voice.set(current or settings["default_voice"])
        self.limit.configure(state="normal")
        self.limit.delete(0, "end")
        self.limit.insert(0, str(settings["daily_char_limit"]))
        if self.limit_locked:
            self.limit.configure(state="disabled")
        self._show_usage(settings)

    def _show_usage(self, settings: dict[str, Any]) -> None:
        used, limit = settings["chars_used_today"], settings["daily_char_limit"]
        self.usage_bar.set(usage_ratio(used, limit))
        color = _WARN_COLOR if limit and used / limit >= 0.8 else theme.ACCENT
        self.usage_bar.configure(progress_color=color)
        self.usage_label.configure(text=f"Đã dùng hôm nay: {format_number(used)} ký tự")

    def _save(self) -> None:
        try:
            limit = int(self.limit.get().strip().replace(".", "") or 0)
            payload = {
                "prefetch_count": int(self.prefetch.get()),
                "default_speed": float(self.speed.get().rstrip("x")),
                "default_voice": self._voice_ids.get(self.voice.get(), self.voice.get()),
                "daily_char_limit": limit,
            }
        except ValueError:
            self.status.configure(text="Giới hạn ký tự phải là số nguyên.", text_color=_ERROR_COLOR)
            return
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.update_settings(payload), self.guard(self._saved), self.guard(self._failed))

    def _saved(self, settings: dict[str, Any]) -> None:
        self.ctx.app.apply_settings(settings)
        self.status.configure(text="Đã lưu cài đặt.", text_color=_OK_COLOR)
        self._show_usage(settings)

    # -- connectivity check ------------------------------------------------------------

    def _set_row(self, key: str, state: str, text: str) -> None:
        icon, detail = self.rows[key]
        symbol, color = {"run": ("⏳", _WARN_COLOR), "ok": ("✔", _OK_COLOR), "fail": ("✖", _ERROR_COLOR)}.get(
            state, ("·", theme.MUTED))
        icon.configure(text=symbol, text_color=color)
        detail.configure(text=f"{self.CHECK_LABELS[key]}  {text}")

    def _run_checks(self) -> None:
        self.check_btn.configure(state="disabled")
        for key in self.CHECKS:
            self._set_row(key, "run", "")

        def work() -> tuple[dict[str, Any], dict[str, Any]]:
            return self.ctx.api.network_health(), self.ctx.api.verify_tts()

        self.ctx.ui.run_in_thread(work, self.guard(self._checks_done), self.guard(self._checks_failed))

    def _checks_failed(self, exc: Exception) -> None:
        self.check_btn.configure(state="normal")
        for key in self.CHECKS:
            self._set_row(key, "fail", error_text(exc))

    def _checks_done(self, result: tuple[dict[str, Any], dict[str, Any]]) -> None:
        network, verify = result
        self.check_btn.configure(state="normal")
        by_name = {c["name"]: c for c in network["checks"]}
        for key in ("dns", "port", "latency"):
            if network["skipped"]:
                self._set_row(key, "ok", "bỏ qua (nhà cung cấp chạy offline)")
            elif key in by_name:
                self._set_row(key, "ok" if by_name[key]["ok"] else "fail", by_name[key]["detail"])
            else:
                self._set_row(key, "fail", "không chạy được vì bước trước lỗi")
        if verify["ok"]:
            self._set_row("synth", "ok", "thành công")
        else:
            self._set_row("synth", "fail", verify.get("error") or "thất bại")


# ============================================================ S06 – Ghi chú mới (từ Phòng Đọc)


class NoteDialog(ModalDialog):
    def __init__(self, master: tk.Misc, ctx: AppContext, book_id: int, sentence_index: int,
                 start: int, end: int, excerpt: str, on_saved: Callable[[], None]):
        super().__init__(master, "Lưu trích dẫn", 520, 390)
        self.ctx, self.on_saved = ctx, on_saved
        self.target = (book_id, sentence_index, start, end)
        self.columnconfigure(0, weight=1)
        _label(self, "Đoạn trích").grid(row=0, column=0, padx=20, pady=(18, 0), sticky="w")
        shown = excerpt if len(excerpt) <= 160 else excerpt[:157] + "…"
        _label(self, f"“{shown}”", wraplength=470, text_color=theme.TEXT_2).grid(
            row=1, column=0, padx=20, sticky="w")
        _label(self, "Ghi chú của bạn").grid(row=2, column=0, padx=20, pady=(12, 0), sticky="w")
        self.box = ctk.CTkTextbox(self, height=90)
        self.box.grid(row=3, column=0, padx=20, sticky="ew")
        _label(self, "Cảm xúc (không bắt buộc)").grid(row=4, column=0, padx=20, pady=(10, 0), sticky="w")
        self.feeling = ctk.CTkSegmentedButton(self, values=[label for _, label in EMOTIONS])
        self.feeling.grid(row=5, column=0, padx=20, sticky="w")
        self.status = _label(self, "", text_color=_ERROR_COLOR, wraplength=470)
        self.status.grid(row=6, column=0, padx=20, pady=(6, 0), sticky="w")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=7, column=0, padx=20, pady=12, sticky="e")
        ctk.CTkButton(buttons, text="Hủy", width=90, **theme.SECONDARY, command=self.close).pack(side="left", padx=(0, 8))
        self.save_btn = ctk.CTkButton(buttons, text="Lưu", width=120, command=self._save)
        self.save_btn.pack(side="left")
        self.box.focus_set()

    def _save(self) -> None:
        self.save_btn.configure(state="disabled")
        text = self.box.get("1.0", "end").strip()
        book_id, sentence, start, end = self.target
        tag = next((value for value, label in EMOTIONS if label == self.feeling.get()), None)
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.create_note(book_id, sentence, start, end, text, emotion_tag=tag),
            self.guard(self._done), self.guard(self._failed))

    def _done(self, _: dict[str, Any]) -> None:
        self.on_saved()
        self.close()

    def _failed(self, exc: Exception) -> None:
        self.save_btn.configure(state="normal")
        self.status.configure(text=error_text(exc))


class EditNoteDialog(ModalDialog):
    def __init__(self, master: tk.Misc, ctx: AppContext, note: dict[str, Any], on_saved: Callable[[], None]):
        super().__init__(master, "Sửa trích dẫn", 520, 330)
        self.ctx, self.note, self.on_saved = ctx, note, on_saved
        self.columnconfigure(0, weight=1)
        _label(self, f"“{note['excerpt']}”", wraplength=470, text_color=theme.TEXT_2).grid(
            row=0, column=0, padx=20, pady=(18, 8), sticky="w")
        self.box = ctk.CTkTextbox(self, height=90)
        self.box.insert("1.0", note["note_text"])
        self.box.grid(row=1, column=0, padx=20, sticky="ew")
        _label(self, "Cảm xúc (không bắt buộc; bấm lại nhãn đang chọn để bỏ)").grid(row=2, column=0, padx=20, pady=(10, 0), sticky="w")
        self.feeling = ctk.CTkSegmentedButton(self, values=[label for _, label in EMOTIONS], command=self._feeling_clicked)
        self.feeling.grid(row=3, column=0, padx=20, sticky="w")
        self._tag: str | None = note.get("emotion_tag")
        if self._tag:
            self.feeling.set(next(label for value, label in EMOTIONS if value == self._tag))
        self.status = _label(self, "", text_color=_ERROR_COLOR)
        self.status.grid(row=4, column=0, padx=20, sticky="w")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=5, column=0, padx=20, pady=12, sticky="e")
        ctk.CTkButton(buttons, text="Hủy", width=90, **theme.SECONDARY, command=self.close).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="Lưu", width=100, command=self._save).pack(side="left")

    def _feeling_clicked(self, label: str) -> None:
        value = next(v for v, text in EMOTIONS if text == label)
        self._tag = None if value == self._tag else value  # the chosen feeling again removes it
        if self._tag is None:
            self.feeling.set("")

    def _save(self) -> None:
        text = self.box.get("1.0", "end").strip()
        tag = self._tag
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.update_note(self.note["id"], note_text=text, emotion_tag=tag),
            self.guard(lambda _: (self.on_saved(), self.close())),
            self.guard(lambda exc: self.status.configure(text=error_text(exc))))


# ============================================================ S01 – Đổi tên tài liệu


class EditBookDialog(ModalDialog):
    """S01 – Sửa thông tin tài liệu: tên, tác giả, thể loại và ảnh bìa."""

    def __init__(self, master: tk.Misc, ctx: AppContext, book: dict[str, Any],
                 on_saved: Callable[[dict[str, Any]], None]):
        super().__init__(master, "Sửa thông tin tài liệu", 480, 450)
        self.ctx, self.book, self.on_saved = ctx, book, on_saved
        self.cover: Path | None = None
        self.columnconfigure(0, weight=1)
        _label(self, "Tên tài liệu").grid(row=0, column=0, padx=20, pady=(20, 0), sticky="w")
        self.entry = ctk.CTkEntry(self)
        self.entry.insert(0, book["title"])
        self.entry.grid(row=1, column=0, padx=20, sticky="ew")
        self.entry.bind("<Return>", lambda _e: self._save())
        _label(self, "Tác giả").grid(row=2, column=0, padx=20, pady=(12, 0), sticky="w")
        self.author_entry = ctk.CTkEntry(self)
        self.author_entry.insert(0, book.get("author") or "")
        self.author_entry.grid(row=3, column=0, padx=20, sticky="ew")
        _label(self, "Thể loại").grid(row=4, column=0, padx=20, pady=(12, 0), sticky="w")
        self.categories = ctx.app.categories
        names = ["(Chưa phân loại)"] + [c["name"] for c in self.categories]
        self.category_box = ctk.CTkComboBox(self, values=names, state="readonly")
        self.category_box.set((book.get("category") or {}).get("name") or names[0])
        self.category_box.grid(row=5, column=0, padx=20, sticky="ew")
        cover_row = ctk.CTkFrame(self, fg_color="transparent")
        cover_row.grid(row=6, column=0, padx=20, pady=(12, 0), sticky="ew")
        cover_row.columnconfigure(1, weight=1)
        CoverView(cover_row, ctx, book["title"], book.get("cover_url"), size=(60, 80)).grid(row=0, column=0, padx=(0, 12))
        self.cover_label = _label(cover_row, "Ảnh bìa hiện tại", text_color=theme.MUTED)
        self.cover_label.grid(row=0, column=1, sticky="w")
        ctk.CTkButton(cover_row, text="Đổi ảnh bìa…", width=120, command=self._choose_cover, **theme.SECONDARY).grid(row=0, column=2)
        self.status = _label(self, "", text_color=_ERROR_COLOR, wraplength=430)
        self.status.grid(row=7, column=0, padx=20, pady=(10, 0), sticky="w")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=8, column=0, padx=20, pady=14, sticky="e")
        ctk.CTkButton(buttons, text="Hủy", width=90, **theme.SECONDARY, command=self.close).pack(side="left", padx=(0, 8))
        self.save_btn = ctk.CTkButton(buttons, text="Lưu", width=100, command=self._save)
        self.save_btn.pack(side="left")
        self.after(200, lambda: (self.entry.focus_set(), self.entry.select_range(0, "end")))

    def _choose_cover(self) -> None:
        chosen = filedialog.askopenfilename(parent=self, title="Chọn ảnh bìa",
                                            filetypes=[("Ảnh JPEG/PNG", "*.jpg *.jpeg *.png"), ("Tất cả", "*.*")])
        if not chosen:
            return
        picked = Path(chosen)
        if picked.stat().st_size > 2 * 1024 * 1024:
            self.status.configure(text="Ảnh bìa tối đa 2 MB.")
            return
        self.cover = picked
        self.cover_label.configure(text=f"Ảnh mới: {picked.name}", text_color=theme.TEXT)
        self.status.configure(text="")

    def _save(self) -> None:
        title, error = check_book_title(self.entry.get())
        if error or title is None:
            self.status.configure(text=error or "")
            return
        category_id = next((c["id"] for c in self.categories if c["name"] == self.category_box.get()), None)
        changes: dict[str, Any] = {}
        if title != self.book["title"]:
            changes["title"] = title
        author = " ".join(self.author_entry.get().split())
        if author != (self.book.get("author") or "").strip():
            changes["author"] = author
        if category_id != (self.book.get("category") or {}).get("id"):
            changes["category_id"] = category_id
        cover = self.cover
        if not changes and not cover:
            self.close()
            return
        self.save_btn.configure(state="disabled")

        def work() -> dict[str, Any]:
            saved = self.ctx.api.update_book(self.book["id"], **changes) if changes else self.book
            return self.ctx.api.replace_cover(self.book["id"], cover) if cover else saved

        self.ctx.ui.run_in_thread(work, self.guard(self._done), self.guard(self._failed))

    def _done(self, saved: dict[str, Any]) -> None:
        self.on_saved(saved)
        self.close()

    def _failed(self, exc: Exception) -> None:
        self.save_btn.configure(state="normal")
        self.status.configure(text=error_text(exc))


class BookPickerDialog(ModalDialog):
    def __init__(self, master: tk.Misc, ctx: AppContext, on_pick: Callable[[dict[str, Any]], None]):
        super().__init__(master, "Chọn tài liệu", 460, 460)
        self.ctx, self.on_pick = ctx, on_pick
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.list = ctk.CTkScrollableFrame(self)
        self.list.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        self.list.columnconfigure(0, weight=1)
        _label(self.list, "Đang tải…").grid(row=0, column=0)
        ctx.ui.run_in_thread(ctx.api.list_books, self.guard(self._loaded),
                             self.guard(lambda exc: _label(self.list, error_text(exc)).grid(row=1, column=0)))

    def _loaded(self, books: list[dict[str, Any]]) -> None:
        for child in self.list.winfo_children():
            child.destroy()
        if not books:
            _label(self.list, "Chưa có tài liệu nào. Hãy thêm ở tab Thư Viện.").grid(row=0, column=0, pady=20)
        for row, book in enumerate(books):
            ctk.CTkButton(
                self.list, anchor="w", text=f"{book['title']}  ·  {format_number(book['total_sentences'])} câu",
                fg_color="transparent", text_color=theme.TEXT, hover_color=theme.SURFACE_3,
                command=lambda b=book: (self.on_pick(b), self.close()),
            ).grid(row=row, column=0, sticky="ew", pady=1)


# ============================================================ S07 – Xuất audio


class ExportDialog(ModalDialog):
    def __init__(self, master: tk.Misc, ctx: AppContext, book: dict[str, Any]):
        super().__init__(master, f"Xuất audio – {book['title']}", 560, 440)
        self.ctx, self.book = ctx, book
        self.job_id: str | None = None
        self.mode = tk.StringVar(value="all")
        self.columnconfigure(0, weight=1)

        _label(self, "Phạm vi", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=20, pady=(18, 2), sticky="w")
        ctk.CTkRadioButton(self, text="Cả tài liệu", variable=self.mode, value="all",
                           command=self._range_changed).grid(row=1, column=0, padx=20, sticky="w")
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=2, column=0, padx=20, pady=4, sticky="w")
        ctk.CTkRadioButton(row, text="Từ câu", variable=self.mode, value="range",
                           command=self._range_changed).pack(side="left")
        self.from_entry = ctk.CTkEntry(row, width=70)
        self.from_entry.insert(0, "1")
        self.from_entry.pack(side="left", padx=6)
        _label(row, "đến câu").pack(side="left")
        self.to_entry = ctk.CTkEntry(row, width=70)
        self.to_entry.insert(0, str(book["total_sentences"]))
        self.to_entry.pack(side="left", padx=6)
        ctk.CTkButton(row, text="Ước tính", width=90, command=self._estimate).pack(side="left", padx=8)

        self.estimate_label = _label(self, "Đang ước tính…", wraplength=510)
        self.estimate_label.grid(row=3, column=0, padx=20, pady=(10, 0), sticky="w")
        self.progress = ctk.CTkProgressBar(self)
        self.progress.set(0)
        self.progress.grid(row=4, column=0, padx=20, pady=(14, 2), sticky="ew")
        self.progress_label = _label(self, "")
        self.progress_label.grid(row=5, column=0, padx=20, sticky="w")
        self.status = _label(self, "", wraplength=510)
        self.status.grid(row=6, column=0, padx=20, pady=6, sticky="w")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=7, column=0, padx=20, pady=14, sticky="e")
        ctk.CTkButton(buttons, text="Đóng", width=90, **theme.SECONDARY, command=self.close).pack(side="left", padx=(0, 8))
        self.start_btn = ctk.CTkButton(buttons, text="Bắt đầu xuất", width=130, command=self._start)
        self.start_btn.pack(side="left")
        self.cancel_btn = ctk.CTkButton(buttons, text="Hủy xuất", width=100, **theme.SECONDARY,
                                        command=self._cancel_export)
        self.save_btn = ctk.CTkButton(buttons, text="Lưu file…", width=110, command=self._save_file)
        self._estimate()

    def _range(self) -> tuple[int, int | None]:
        if self.mode.get() == "all":
            return 0, None
        start, end = int(self.from_entry.get()), int(self.to_entry.get())
        if start < 1 or end < start:
            raise ValueError("Khoảng câu không hợp lệ.")
        return start - 1, end - 1

    def _range_changed(self) -> None:
        self._estimate()

    def _estimate(self) -> None:
        try:
            start, end = self._range()
        except ValueError as exc:
            self.estimate_label.configure(text=str(exc) or "Khoảng câu phải là số.", text_color=_ERROR_COLOR)
            return
        self.estimate_label.configure(text="Đang ước tính…", text_color=theme.TEXT)
        voice = self.ctx.app.current_voice_id
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.export_estimate(self.book["id"], start, end, voice),
            self.guard(self._show_estimate),
            self.guard(lambda exc: self.estimate_label.configure(text=error_text(exc), text_color=_ERROR_COLOR)))

    def _show_estimate(self, est: dict[str, Any]) -> None:
        text = (f"~ {format_number(est['sentences'])} câu · ~ {est['estimated_minutes']:.0f} phút · "
                f"{format_number(est['chars_to_synthesize'])} ký tự cần gọi API "
                f"({format_number(est['chars_cached'])} lấy từ cache)")
        limit = est["daily_limit"]
        over = limit and est["chars_used_today"] + est["chars_to_synthesize"] > limit
        if over:
            text += "\nVượt giới hạn ký tự hôm nay: chỉ xuất được phần đã có trong cache."
        self.estimate_label.configure(text=text, text_color=_WARN_COLOR if over else theme.TEXT)

    def _start(self) -> None:
        try:
            start, end = self._range()
        except ValueError as exc:
            self.status.configure(text=str(exc) or "Khoảng câu phải là số.", text_color=_ERROR_COLOR)
            return
        self.start_btn.configure(state="disabled")
        self.status.configure(text="Đang xuất…", text_color=theme.TEXT)
        voice = self.ctx.app.current_voice_id
        character = self.ctx.app.settings.get("character_voice") or None  # the export is read by the same two voices
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.start_export(self.book["id"], start, end, voice, character),
            self.guard(self._started), self.guard(self._start_failed))

    def _start_failed(self, exc: Exception) -> None:
        self.start_btn.configure(state="normal")
        self.status.configure(text=error_text(exc), text_color=_ERROR_COLOR)

    def _started(self, job: dict[str, Any]) -> None:
        self.job_id = job["job_id"]
        self.cancel_btn.configure(state="normal", text="Hủy xuất")
        self.cancel_btn.pack(side="left", padx=(8, 0))
        self._poll()

    def _cancel_export(self) -> None:
        if not self.job_id:
            return
        job_id = self.job_id
        self.cancel_btn.configure(state="disabled", text="Đang hủy…")
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.cancel_export(job_id), lambda _job: None, self.guard(self._start_failed))

    def _poll(self) -> None:
        if not self.job_id:
            return
        job_id = self.job_id
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.export_status(job_id), self.guard(self._progress), self.guard(self._start_failed))

    def _progress(self, job: dict[str, Any]) -> None:
        total = max(job["total"], 1)
        self.progress.set(job["done"] / total)
        self.progress_label.configure(text=f"{job['done']} / {job['total']} câu")
        if job["status"] == "running":
            self.after(800, self._poll)
            return
        self.cancel_btn.pack_forget()
        if job["status"] == "cancelled":
            self.start_btn.configure(state="normal")
            self.progress.set(0)
            self.status.configure(text="Đã hủy xuất. Phần đã tổng hợp vẫn nằm trong cache.", text_color=_WARN_COLOR)
        elif job["status"] == "done":
            self.status.configure(text=f"✔ Hoàn tất. {job['file_name']}", text_color=_OK_COLOR)
            self.file_name = job["file_name"]
            self.save_btn.pack(side="left", padx=(8, 0))
        else:
            self.start_btn.configure(state="normal")
            self.status.configure(text=f"Xuất thất bại: {job['error']}", text_color=_ERROR_COLOR)

    def _save_file(self) -> None:
        name = getattr(self, "file_name", "audiobook.wav")
        target = filedialog.asksaveasfilename(
            parent=self, initialfile=name, defaultextension=Path(name).suffix)
        if not target or not self.job_id:
            return
        job_id = self.job_id
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.download_export(job_id, target),
            self.guard(lambda _: self.status.configure(text=f"Đã lưu: {target}", text_color=_OK_COLOR)),
            self.guard(self._start_failed))


class AmbientDialog(ModalDialog):
    """Âm thanh nền: choose a sound from the library, its volume, and the chapter chime. Saved as you change them."""

    def __init__(self, master: tk.Misc, ctx: AppContext, on_changed: Callable[[], None]):
        super().__init__(master, "Âm thanh nền", 460, 500)
        self.ctx, self.on_changed = ctx, on_changed
        settings = ctx.app.settings
        self.choice = tk.StringVar(value=str(settings.get("ambient_track") or 0))
        self.chime = tk.BooleanVar(value=bool(settings.get("chapter_chime", True)))
        self._save_job: str | None = None
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent", height=200)
        self.list.grid(row=0, column=0, padx=16, pady=(16, 4), sticky="nsew")
        _label(self.list, "Đang tải…", text_color=theme.MUTED).pack(anchor="w", pady=6)
        self.volume_label = _label(self, "", text_color=theme.TEXT_2)
        self.volume_label.grid(row=1, column=0, padx=20, pady=(8, 0), sticky="w")
        self.slider = ctk.CTkSlider(self, from_=0, to=100, number_of_steps=20, command=self._volume_moved)
        self.slider.set(float(settings.get("ambient_volume", 0.4)) * 100)
        self.slider.grid(row=2, column=0, padx=20, sticky="ew")
        ctk.CTkCheckBox(self, text="Phát tiếng chuông khi sang chương mới", variable=self.chime,
                        command=self._chime_changed).grid(row=3, column=0, padx=20, pady=12, sticky="w")
        self.status = _label(self, "", text_color=_ERROR_COLOR, wraplength=410)
        self.status.grid(row=4, column=0, padx=20, sticky="w")
        ctk.CTkButton(self, text="Xong", width=90, command=self.close).grid(row=5, column=0, padx=20, pady=14, sticky="e")
        self._show_volume()
        ctx.ui.run_in_thread(ctx.api.list_ambient, self.guard(self._loaded), self.guard(self._failed))

    def _loaded(self, tracks: list[dict[str, Any]]) -> None:
        for child in self.list.winfo_children():
            child.destroy()
        ctk.CTkRadioButton(self.list, text="Tắt", variable=self.choice, value="0", command=self._track_changed).pack(anchor="w", pady=3)
        for track in tracks:
            ctk.CTkRadioButton(self.list, text=track["name"], variable=self.choice, value=str(track["id"]),
                               command=self._track_changed).pack(anchor="w", pady=3)
        if not tracks:
            _label(self.list, "Quản trị viên chưa thêm âm thanh nền nào.", text_color=theme.MUTED).pack(anchor="w", pady=6)

    def _failed(self, exc: Exception) -> None:
        self.status.configure(text=error_text(exc))

    def _show_volume(self) -> None:
        self.volume_label.configure(text=f"Âm lượng nền: {round(self.slider.get())}%")

    def _volume_moved(self, _value: float) -> None:
        self._show_volume()
        self._apply_now()
        if self._save_job:
            self.after_cancel(self._save_job)
        self._save_job = self.after(400, self._save)  # save when the slider rests, not on every step

    def _track_changed(self) -> None:
        self._apply_now()
        self._save()

    def _chime_changed(self) -> None:
        self._apply_now()
        self._save()

    def _values(self) -> dict[str, Any]:
        return {"ambient_track": int(self.choice.get() or 0), "ambient_volume": round(self.slider.get()) / 100,
                "chapter_chime": bool(self.chime.get())}

    def _apply_now(self) -> None:
        """Hear the change at once, before the server has answered."""
        self.ctx.app.apply_settings({**self.ctx.app.settings, **self._values()})

    def _save(self) -> None:
        self._save_job = None
        payload = {**{k: self.ctx.app.settings[k] for k in ("prefetch_count", "default_speed", "default_voice", "daily_char_limit")},
                   **self._values()}

        def saved(result: dict[str, Any]) -> None:
            self.status.configure(text="")
            self.ctx.app.apply_settings(result)
            self.on_changed()

        self.ctx.ui.run_in_thread(lambda: self.ctx.api.update_settings(payload), self.guard(saved), self.guard(self._failed))


class AddAmbientDialog(ModalDialog):
    """Admin: add a background sound to the library (a file from disk and a display name)."""

    def __init__(self, master: tk.Misc, ctx: AppContext, on_done: Callable[[], None]):
        super().__init__(master, "Thêm âm thanh nền", 480, 300)
        self.ctx, self.on_done = ctx, on_done
        self.path: Path | None = None
        self.columnconfigure(0, weight=1)
        _label(self, "File âm thanh (MP3, OGG, WAV, M4A · tối đa 15 MB)").grid(row=0, column=0, padx=20, pady=(20, 0), sticky="w")
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=1, column=0, padx=20, sticky="ew")
        row.columnconfigure(0, weight=1)
        self.file_label = _label(row, "Chưa chọn file")
        self.file_label.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(row, text="Chọn file…", width=110, command=self._choose).grid(row=0, column=1)
        _label(self, "Tên hiển thị").grid(row=2, column=0, padx=20, pady=(12, 0), sticky="w")
        self.name_entry = ctk.CTkEntry(self)
        self.name_entry.grid(row=3, column=0, padx=20, sticky="ew")
        self.status = _label(self, "", text_color=_ERROR_COLOR, wraplength=430)
        self.status.grid(row=4, column=0, padx=20, pady=(8, 0), sticky="w")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=5, column=0, padx=20, pady=14, sticky="e")
        ctk.CTkButton(buttons, text="Hủy", width=90, **theme.SECONDARY, command=self.close).pack(side="left", padx=(0, 8))
        self.add_btn = ctk.CTkButton(buttons, text="Thêm", width=100, state="disabled", command=self._add)
        self.add_btn.pack(side="left")

    def _choose(self) -> None:
        chosen = filedialog.askopenfilename(parent=self, title="Chọn file âm thanh",
                                            filetypes=[("Âm thanh", "*.mp3 *.ogg *.wav *.m4a")])
        if not chosen:
            return
        picked = Path(chosen)
        if picked.stat().st_size > 15 * 1024 * 1024:
            self.status.configure(text="File vượt quá 15 MB.")
            return
        self.path = picked
        self.file_label.configure(text=picked.name)
        if not self.name_entry.get().strip():
            self.name_entry.insert(0, picked.stem.replace("_", " ")[:100])
        self.status.configure(text="")
        self.add_btn.configure(state="normal")

    def _add(self) -> None:
        name, path = self.name_entry.get().strip(), self.path
        if not name or path is None:
            self.status.configure(text="Hãy chọn file và nhập tên.")
            return
        self.add_btn.configure(state="disabled")
        self.status.configure(text="Đang tải lên…", text_color=_WARN_COLOR)
        self.ctx.ui.run_in_thread(lambda: self.ctx.api.add_ambient(path, name), self.guard(self._done), self.guard(self._failed))

    def _done(self, _track: dict[str, Any]) -> None:
        self.on_done()
        self.close()

    def _failed(self, exc: Exception) -> None:
        self.add_btn.configure(state="normal")
        self.status.configure(text=error_text(exc), text_color=_ERROR_COLOR)


class SleepTimerDialog(ModalDialog):
    """Hẹn giờ tắt: a countdown, or stop at the end of this chapter. The last 10 s fade out."""

    def __init__(self, master: tk.Misc, ctx: AppContext, on_change: Callable[[], None]):
        super().__init__(master, "Hẹn giờ tắt", 440, 400)
        self.ctx, self.on_change = ctx, on_change
        timer = ctx.reader.sleep
        self.columnconfigure((0, 1), weight=1)
        _label(self, "Âm lượng giảm dần trong 10 giây cuối rồi tự tạm dừng và lưu vị trí đọc.",
               text_color=theme.TEXT_2, wraplength=390).grid(
            row=0, column=0, columnspan=2, padx=20, pady=(20, 10), sticky="w")
        for number, minutes in enumerate(MINUTE_PRESETS):
            selected = timer.mode == "minutes" and timer.minutes == minutes
            ctk.CTkButton(self, text=f"{minutes} phút", height=40, command=lambda m=minutes: self._minutes(m),
                          **(theme.ACCENT_SOFT_BUTTON if selected else theme.SECONDARY)).grid(
                row=1 + number // 2, column=number % 2, padx=(20, 6) if number % 2 == 0 else (6, 20), pady=4, sticky="ew")

        custom = ctk.CTkFrame(self, fg_color="transparent")
        custom.grid(row=3, column=0, columnspan=2, padx=20, pady=(8, 4), sticky="w")
        _label(custom, "Tùy chỉnh").pack(side="left")
        self.custom_entry = ctk.CTkEntry(custom, width=90, placeholder_text=f"1–{CUSTOM_MINUTES_MAX}")
        self.custom_entry.pack(side="left", padx=8)
        self.custom_entry.bind("<Return>", lambda _e: self._custom())
        _label(custom, "phút").pack(side="left")
        ctk.CTkButton(custom, text="Đặt", width=60, command=self._custom, **theme.SECONDARY).pack(side="left", padx=8)

        ctk.CTkButton(self, text="Dừng khi hết chương này", height=40, command=self._chapter,
                      **(theme.ACCENT_SOFT_BUTTON if timer.mode == "chapter" else theme.SECONDARY)).grid(
            row=4, column=0, columnspan=2, padx=20, pady=8, sticky="ew")
        self.status = _label(self, "", text_color=_ERROR_COLOR)
        self.status.grid(row=5, column=0, columnspan=2, padx=20, sticky="w")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=6, column=0, columnspan=2, padx=20, pady=12, sticky="ew")
        self.off_btn = ctk.CTkButton(buttons, text="Tắt hẹn giờ", width=110, command=self._off,
                                     state="normal" if timer.active else "disabled", **theme.GHOST)
        self.off_btn.pack(side="left")
        ctk.CTkButton(buttons, text="Đóng", width=90, command=self.close, **theme.SECONDARY).pack(side="right")

    def _apply(self, action: Callable[[], None]) -> None:
        action()
        self.on_change()
        self.close()

    def _minutes(self, minutes: int) -> None:
        self._apply(lambda: self.ctx.reader.sleep_minutes(minutes))

    def _custom(self) -> None:
        minutes = parse_custom_minutes(self.custom_entry.get())
        if minutes is None:
            self.status.configure(text=f"Nhập số phút nguyên từ 1 đến {CUSTOM_MINUTES_MAX}.")
            return
        self._minutes(minutes)

    def _chapter(self) -> None:
        self._apply(self.ctx.reader.sleep_chapter)

    def _off(self) -> None:
        self._apply(self.ctx.reader.sleep_cancel)


class ChapterListDialog(ModalDialog):
    """Mục lục: pick a chapter to start playing from its first sentence."""

    def __init__(self, master: tk.Misc, ctx: AppContext, chapters: list[dict[str, Any]], current: int | None,
                 on_pick: Callable[[dict[str, Any]], None]):
        super().__init__(master, "Mục lục", 520, 560)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        listing = ctk.CTkScrollableFrame(self, fg_color="transparent")
        listing.grid(row=0, column=0, padx=16, pady=(16, 6), sticky="nsew")
        listing.columnconfigure(0, weight=1)
        for row, chapter in enumerate(chapters):
            is_current = chapter["chapter_index"] == current
            item = ctk.CTkFrame(listing, corner_radius=10, fg_color=theme.ACCENT_SOFT if is_current else "transparent")
            item.grid(row=row, column=0, sticky="ew", pady=2)
            title = ctk.CTkLabel(item, text=chapter["title"], anchor="w", justify="left", wraplength=420,
                                 font=theme.font(13, "bold" if is_current else "normal"),
                                 text_color=theme.ACCENT if is_current else theme.TEXT)
            title.pack(fill="x", padx=14, pady=(8, 0))
            meta = ctk.CTkLabel(item, text=describe_chapter(chapter, format_number), anchor="w",
                                text_color=theme.MUTED, font=theme.font(11))
            meta.pack(fill="x", padx=14, pady=(0, 8))
            for widget in (item, title, meta):  # the whole row is the button
                widget.bind("<Button-1>", lambda _e, c=chapter: (on_pick(c), self.close()))
                widget.configure(cursor="hand2")
                if not is_current:
                    widget.bind("<Enter>", lambda _e, f=item: f.configure(fg_color=theme.SURFACE_2))
                    widget.bind("<Leave>", lambda _e, f=item: f.configure(fg_color="transparent"))
        ctk.CTkButton(self, text="Đóng", width=90, command=self.close, **theme.SECONDARY).grid(
            row=1, column=0, padx=16, pady=(4, 14), sticky="e")
