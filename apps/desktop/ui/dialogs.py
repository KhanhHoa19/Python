"""Modal dialogs: S02 upload, S04 voices (+clone), S05 connection & settings, S06 note, S07 export."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

import customtkinter as ctk

import config
from ui.common import AppContext, ModalDialog, error_text
from ui.viewmodels import describe_voice, format_number, usage_ratio

_ERROR_COLOR = "#d64545"
_OK_COLOR = "#2e9d57"
_WARN_COLOR = "#e08a1e"


def _label(master: tk.Misc, text: str, **kwargs: Any) -> ctk.CTkLabel:
    return ctk.CTkLabel(master, text=text, anchor="w", justify="left", **kwargs)


# ============================================================ S02 – Thêm tài liệu


class UploadDialog(ModalDialog):
    def __init__(self, master: tk.Misc, ctx: AppContext, on_done: Callable[[dict[str, Any]], None]):
        super().__init__(master, "Thêm tài liệu", 520, 360)
        self.ctx, self.on_done = ctx, on_done
        self.path: Path | None = None
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

        self.status = _label(self, "", text_color=_ERROR_COLOR, wraplength=470)
        self.status.grid(row=6, column=0, padx=20, pady=(10, 0), sticky="w")
        self.progress = ctk.CTkProgressBar(self, mode="indeterminate")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=8, column=0, padx=20, pady=16, sticky="e")
        self.cancel_btn = ctk.CTkButton(buttons, text="Hủy", width=90, fg_color="gray40", command=self.close)
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

    def _upload(self) -> None:
        if not self.path:
            return
        if self.path.stat().st_size > 10 * 1024 * 1024:
            self.status.configure(text="File vượt quá 10 MB.")
            return
        self.upload_btn.configure(state="disabled")
        self.status.configure(text="Đang tải lên và tách câu…", text_color=("gray20", "gray80"))
        self.progress.grid(row=7, column=0, padx=20, sticky="ew")
        self.progress.start()
        path, title, author = self.path, self.title_entry.get().strip(), self.author_entry.get().strip()
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.ingest_book(path, title, author),
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


# ============================================================ S04 – Giọng đọc


class VoicesDialog(ModalDialog):
    """Pick a voice (with preview) and manage custom voices."""

    def __init__(self, master: tk.Misc, ctx: AppContext, on_select: Callable[[str], None]):
        super().__init__(master, "Giọng đọc", 640, 520)
        self.ctx, self.on_select = ctx, on_select
        self.data: dict[str, Any] = {}
        self.choice = tk.StringVar(value=ctx.app.current_voice_id or "")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.notice = _label(self, "Đang tải danh sách giọng…", text_color=_WARN_COLOR, wraplength=600)
        self.notice.grid(row=0, column=0, padx=16, pady=(12, 0), sticky="ew")
        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=1, column=0, padx=16, pady=8, sticky="nsew")
        self.builtin_list = self._make_list(self.tabs.add("Có sẵn"))
        self.custom_list = self._make_list(self.tabs.add("Giọng của tôi"))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="ew")
        self.add_btn = ctk.CTkButton(bar, text="+ Thêm giọng mới", command=self._open_clone, state="disabled")
        self.add_btn.pack(side="left")
        ctk.CTkButton(bar, text="Dùng giọng này", width=130, command=self._use).pack(side="right")
        ctk.CTkButton(bar, text="Hủy", width=80, fg_color="gray40", command=self.close).pack(side="right", padx=8)
        self.reload()

    @staticmethod
    def _make_list(tab: ctk.CTkFrame) -> ctk.CTkScrollableFrame:
        frame = ctk.CTkScrollableFrame(tab)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        return frame

    def reload(self) -> None:
        self.ctx.ui.run_in_thread(self.ctx.api.list_voices, self.guard(self._loaded), self.guard(self._load_failed))

    def _load_failed(self, exc: Exception) -> None:
        self.notice.configure(text=error_text(exc), text_color=_ERROR_COLOR)

    def _loaded(self, data: dict[str, Any]) -> None:
        self.data = data
        self.ctx.app.set_voices(data)
        self.notice.configure(text=data.get("warning") or "", text_color=_WARN_COLOR)
        if data["supports_cloning"]:
            self.add_btn.configure(state="normal")
        else:
            self.add_btn.configure(state="disabled")
            self.notice.configure(text=(data.get("warning") or "") + " Nhà cung cấp hiện tại không hỗ trợ tạo giọng.")
        for frame, custom in ((self.builtin_list, False), (self.custom_list, True)):
            for child in frame.winfo_children():
                child.destroy()
            voices = [v for v in data["voices"] if bool(v["is_custom"]) is custom]
            if not voices:
                _label(frame, "Bạn chưa có giọng riêng nào." if custom else "Chưa có giọng nào.").grid(
                    row=0, column=0, pady=20)
            for row, voice in enumerate(voices):
                self._voice_row(frame, row, voice)

    def _voice_row(self, frame: ctk.CTkScrollableFrame, row: int, voice: dict[str, Any]) -> None:
        line = ctk.CTkFrame(frame, fg_color="transparent")
        line.grid(row=row, column=0, sticky="ew", pady=2)
        line.columnconfigure(0, weight=1)
        ctk.CTkRadioButton(line, text=describe_voice(voice), variable=self.choice, value=voice["voice_id"]).grid(
            row=0, column=0, sticky="w")
        ctk.CTkButton(line, text="▶ Nghe thử", width=96, command=lambda v=voice["voice_id"]: self._preview(v)).grid(
            row=0, column=1, padx=4)
        if voice["is_custom"]:
            ctk.CTkButton(line, text="🗑", width=36, fg_color=_ERROR_COLOR,
                          command=lambda v=voice: self._delete(v)).grid(row=0, column=2)

    def _preview(self, voice_id: str) -> None:
        self.notice.configure(text="Đang tải giọng nghe thử…", text_color=_WARN_COLOR)

        def work() -> None:
            data, ext = self.ctx.api.preview_voice(voice_id)
            self.ctx.output.play(data, ext)

        self.ctx.ui.run_in_thread(
            work, self.guard(lambda _: self.notice.configure(text="")), self.guard(self._load_failed))

    def _delete(self, voice: dict[str, Any]) -> None:
        if not messagebox.askyesno("Xóa giọng", f'Xóa giọng "{voice["display_name"]}"?', parent=self):
            return
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.delete_voice(voice["voice_id"]),
            self.guard(lambda _: self.reload()), self.guard(self._load_failed))

    def _use(self) -> None:
        if self.choice.get():
            self.on_select(self.choice.get())
        self.close()

    def _open_clone(self) -> None:
        CloneVoiceDialog(self, self.ctx, on_created=self._cloned)

    def _cloned(self, voice: dict[str, Any]) -> None:
        self.choice.set(voice["voice_id"])
        self.tabs.set("Giọng của tôi")
        self.reload()
        self.ctx.app.toast(f'Đã tạo giọng "{voice["display_name"]}"')


class CloneVoiceDialog(ModalDialog):
    def __init__(self, master: tk.Misc, ctx: AppContext, on_created: Callable[[dict[str, Any]], None]):
        super().__init__(master, "Thêm giọng mới", 520, 420)
        self.ctx, self.on_created = ctx, on_created
        self.sample: Path | None = None
        self.consent = tk.BooleanVar(value=False)
        self.columnconfigure(0, weight=1)

        _label(self, "Tên giọng").grid(row=0, column=0, padx=20, pady=(20, 0), sticky="w")
        self.name_entry = ctk.CTkEntry(self)
        self.name_entry.grid(row=1, column=0, padx=20, sticky="ew")
        _label(self, "File mẫu (5–15 giây, WAV/MP3)").grid(row=2, column=0, padx=20, pady=(12, 0), sticky="w")
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
        ctk.CTkButton(buttons, text="Hủy", width=90, fg_color="gray40", command=self.close).pack(side="left", padx=(0, 8))
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
    CHECK_LABELS = {"dns": "DNS", "port": "Cổng 443", "latency": "Độ trễ mạng", "synth": "Thử đọc 1 câu"}

    def __init__(self, master: tk.Misc, ctx: AppContext):
        super().__init__(master, "Kết nối & Cài đặt", 560, 640)
        self.ctx = ctx
        self.columnconfigure(0, weight=1)

        _label(self, "KẾT NỐI", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=20, pady=(16, 4), sticky="w")
        self.provider = _label(self, "Nhà cung cấp: …")
        self.provider.grid(row=1, column=0, padx=20, sticky="w")
        _label(self, "API Key đặt trong file .env phía backend, không nhập ở đây.",
               text_color=("gray40", "gray60")).grid(row=2, column=0, padx=20, sticky="w")
        self.check_btn = ctk.CTkButton(self, text="Kiểm tra kết nối", command=self._run_checks)
        self.check_btn.grid(row=3, column=0, padx=20, pady=8, sticky="w")
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.grid(row=4, column=0, padx=20, sticky="ew")
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
        _label(form, "(0 = không giới hạn)", text_color=("gray40", "gray60")).grid(row=3, column=1, sticky="e")

        self.usage_label = _label(self, "")
        self.usage_label.grid(row=7, column=0, padx=20, pady=(10, 0), sticky="w")
        self.usage_bar = ctk.CTkProgressBar(self)
        self.usage_bar.grid(row=8, column=0, padx=20, pady=4, sticky="ew")
        self.usage_bar.set(0)

        self.status = _label(self, "", wraplength=500)
        self.status.grid(row=9, column=0, padx=20, pady=(8, 0), sticky="w")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=10, column=0, padx=20, pady=16, sticky="e")
        ctk.CTkButton(buttons, text="Đóng", width=90, fg_color="gray40", command=self.close).pack(side="left", padx=(0, 8))
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
        self.limit.delete(0, "end")
        self.limit.insert(0, str(settings["daily_char_limit"]))
        self._show_usage(settings)

    def _show_usage(self, settings: dict[str, Any]) -> None:
        used, limit = settings["chars_used_today"], settings["daily_char_limit"]
        self.usage_bar.set(usage_ratio(used, limit))
        color = _WARN_COLOR if limit and used / limit >= 0.8 else ("#3b8ed0", "#1f6aa5")
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
            state, ("·", "gray50"))
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
        super().__init__(master, "Ghi chú mới", 520, 330)
        self.ctx, self.on_saved = ctx, on_saved
        self.target = (book_id, sentence_index, start, end)
        self.columnconfigure(0, weight=1)
        _label(self, "Đoạn đã chọn").grid(row=0, column=0, padx=20, pady=(18, 0), sticky="w")
        shown = excerpt if len(excerpt) <= 160 else excerpt[:157] + "…"
        _label(self, f"“{shown}”", wraplength=470, text_color=("gray30", "gray70")).grid(
            row=1, column=0, padx=20, sticky="w")
        _label(self, "Ghi chú của bạn").grid(row=2, column=0, padx=20, pady=(12, 0), sticky="w")
        self.box = ctk.CTkTextbox(self, height=90)
        self.box.grid(row=3, column=0, padx=20, sticky="ew")
        self.status = _label(self, "", text_color=_ERROR_COLOR, wraplength=470)
        self.status.grid(row=4, column=0, padx=20, pady=(6, 0), sticky="w")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=5, column=0, padx=20, pady=12, sticky="e")
        ctk.CTkButton(buttons, text="Hủy", width=90, fg_color="gray40", command=self.close).pack(side="left", padx=(0, 8))
        self.save_btn = ctk.CTkButton(buttons, text="Lưu ghi chú", width=120, command=self._save)
        self.save_btn.pack(side="left")
        self.box.focus_set()

    def _save(self) -> None:
        self.save_btn.configure(state="disabled")
        text = self.box.get("1.0", "end").strip()
        book_id, sentence, start, end = self.target
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.create_note(book_id, sentence, start, end, text),
            self.guard(self._done), self.guard(self._failed))

    def _done(self, _: dict[str, Any]) -> None:
        self.on_saved()
        self.close()

    def _failed(self, exc: Exception) -> None:
        self.save_btn.configure(state="normal")
        self.status.configure(text=error_text(exc))


class EditNoteDialog(ModalDialog):
    def __init__(self, master: tk.Misc, ctx: AppContext, note: dict[str, Any], on_saved: Callable[[], None]):
        super().__init__(master, "Sửa ghi chú", 520, 260)
        self.ctx, self.note, self.on_saved = ctx, note, on_saved
        self.columnconfigure(0, weight=1)
        _label(self, f"“{note['excerpt']}”", wraplength=470, text_color=("gray30", "gray70")).grid(
            row=0, column=0, padx=20, pady=(18, 8), sticky="w")
        self.box = ctk.CTkTextbox(self, height=90)
        self.box.insert("1.0", note["note_text"])
        self.box.grid(row=1, column=0, padx=20, sticky="ew")
        self.status = _label(self, "", text_color=_ERROR_COLOR)
        self.status.grid(row=2, column=0, padx=20, sticky="w")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=3, column=0, padx=20, pady=12, sticky="e")
        ctk.CTkButton(buttons, text="Hủy", width=90, fg_color="gray40", command=self.close).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="Lưu", width=100, command=self._save).pack(side="left")

    def _save(self) -> None:
        text = self.box.get("1.0", "end").strip()
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.update_note(self.note["id"], text),
            self.guard(lambda _: (self.on_saved(), self.close())),
            self.guard(lambda exc: self.status.configure(text=error_text(exc))))


# ============================================================ chọn tài liệu (Phòng Đọc → Đổi tài liệu)


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
                fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray80", "gray25"),
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
        ctk.CTkButton(buttons, text="Đóng", width=90, fg_color="gray40", command=self.close).pack(side="left", padx=(0, 8))
        self.start_btn = ctk.CTkButton(buttons, text="Bắt đầu xuất", width=130, command=self._start)
        self.start_btn.pack(side="left")
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
        self.estimate_label.configure(text="Đang ước tính…", text_color=("gray10", "gray90"))
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
        self.estimate_label.configure(text=text, text_color=_WARN_COLOR if over else ("gray10", "gray90"))

    def _start(self) -> None:
        try:
            start, end = self._range()
        except ValueError as exc:
            self.status.configure(text=str(exc) or "Khoảng câu phải là số.", text_color=_ERROR_COLOR)
            return
        self.start_btn.configure(state="disabled")
        self.status.configure(text="Đang xuất…", text_color=("gray10", "gray90"))
        voice = self.ctx.app.current_voice_id
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.start_export(self.book["id"], start, end, voice),
            self.guard(self._started), self.guard(self._start_failed))

    def _start_failed(self, exc: Exception) -> None:
        self.start_btn.configure(state="normal")
        self.status.configure(text=error_text(exc), text_color=_ERROR_COLOR)

    def _started(self, job: dict[str, Any]) -> None:
        self.job_id = job["job_id"]
        self._poll()

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
