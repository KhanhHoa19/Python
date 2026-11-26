"""S03 – Phòng Đọc: karaoke text view, transport controls, speed, jump, notes."""

from __future__ import annotations

import tkinter as tk
from typing import Any

import customtkinter as ctk

import config
from ui.common import AppContext
from ui.dialogs import BookPickerDialog, NoteDialog
from ui.viewmodels import describe_voice, format_number

WINDOW_RADIUS = 60  # sentences rendered on each side of the current one
_ADD_VOICE = "+ Thêm giọng mới…"
_STATE_TEXT = {"playing": "● Đang phát", "paused": "❚❚ Tạm dừng", "stopped": "■ Đã dừng", "finished": "✔ Đã đọc xong"}


class ReaderTab(ctk.CTkFrame):
    """Also implements ReaderListener: controller events arrive on worker threads and are re-posted."""

    def __init__(self, master: tk.Misc, ctx: AppContext):
        super().__init__(master, fg_color="transparent")
        self.ctx = ctx
        self._window: tuple[int, int] | None = None
        self._voice_by_label: dict[str, str] = {}
        self._state = "stopped"
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self._build()
        self.after(500, self._tick_status)

    # -- layout -------------------------------------------------------------------------------

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        header.columnconfigure(0, weight=1)
        self.title_label = ctk.CTkLabel(header, text="Chưa chọn tài liệu", anchor="w",
                                        font=ctk.CTkFont(size=16, weight="bold"))
        self.title_label.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(header, text="Đổi tài liệu", width=110, command=self._pick_book).grid(row=0, column=1, padx=6)
        ctk.CTkLabel(header, text="Giọng:").grid(row=0, column=2, padx=(10, 4))
        self.voice_box = ctk.CTkComboBox(header, values=[""], width=260, state="readonly", command=self._voice_chosen)
        self.voice_box.grid(row=0, column=3)

        self.text = ctk.CTkTextbox(self, wrap="word", font=ctk.CTkFont(size=16), spacing3=6)
        self.text.grid(row=1, column=0, sticky="nsew", padx=12, pady=4)
        self.text.tag_config("current", background="#f5d142", foreground="#000000")
        self.text.tag_config("done", foreground="#8a8a8a")
        self.text.bind("<ButtonRelease-1>", self._on_text_click)
        self.text.configure(state="disabled")
        self.empty_hint = ctk.CTkLabel(self, text="Chưa chọn tài liệu. Bấm “Đổi tài liệu” hoặc mở tab Thư Viện.")
        self.empty_hint.grid(row=1, column=0)

        note_row = ctk.CTkFrame(self, fg_color="transparent")
        note_row.grid(row=2, column=0, sticky="e", padx=12)
        self.note_btn = ctk.CTkButton(note_row, text="📝 Ghi chú đoạn đã chọn", state="disabled", command=self._note)
        self.note_btn.pack()

        self.progress = ctk.CTkProgressBar(self)
        self.progress.set(0)
        self.progress.grid(row=3, column=0, sticky="ew", padx=12, pady=(6, 0))
        self.position_label = ctk.CTkLabel(self, text="Câu 0 / 0", anchor="w")
        self.position_label.grid(row=4, column=0, sticky="w", padx=12)

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=5, column=0, pady=4)
        reader = self.ctx.reader
        for text, command in (
            ("⏮", lambda: reader.jump(0)), ("⏪ Câu trước", reader.previous),
        ):
            ctk.CTkButton(controls, text=text, width=100 if "Câu" in text else 50, command=command).pack(side="left", padx=3)
        self.play_btn = ctk.CTkButton(controls, text="▶", width=70, command=self._toggle)
        self.play_btn.pack(side="left", padx=3)
        for text, command in (
            ("Câu sau ⏩", reader.next), ("⏭", lambda: reader.jump(max(reader.total - 1, 0))),
        ):
            ctk.CTkButton(controls, text=text, width=100 if "Câu" in text else 50, command=command).pack(side="left", padx=3)

        options = ctk.CTkFrame(self, fg_color="transparent")
        options.grid(row=6, column=0, pady=2)
        ctk.CTkLabel(options, text="Tốc độ:").pack(side="left", padx=(0, 6))
        self.speed_buttons = ctk.CTkSegmentedButton(
            options, values=[f"{s}x" for s in config.SPEED_LEVELS], command=self._speed_chosen)
        self.speed_buttons.set("1.0x")
        self.speed_buttons.pack(side="left")
        ctk.CTkLabel(options, text="   Nhảy tới câu:").pack(side="left")
        self.jump_entry = ctk.CTkEntry(options, width=70)
        self.jump_entry.pack(side="left", padx=4)
        self.jump_entry.bind("<Return>", lambda _e: self._jump_from_entry())
        ctk.CTkButton(options, text="Đi", width=44, command=self._jump_from_entry).pack(side="left")

        self.status_label = ctk.CTkLabel(self, text="", anchor="w", text_color=("gray35", "gray65"))
        self.status_label.grid(row=7, column=0, sticky="ew", padx=12, pady=(2, 8))

    # -- ReaderListener (called from any thread) ----------------------------------------------------

    def on_position(self, index: int) -> None:
        self.ctx.ui.post(self._show_position, index)

    def on_state(self, state: str) -> None:
        self.ctx.ui.post(self._show_state, state)

    def on_warning(self, message: str) -> None:
        self.ctx.ui.post(self.ctx.app.toast, message)

    def on_error(self, message: str) -> None:
        self.ctx.ui.post(self.ctx.app.show_error, message)

    # -- book / voice management ------------------------------------------------------------------------

    def show_book(self, start_index: int) -> None:
        book = self.ctx.reader.book
        assert book is not None
        self.title_label.configure(text=book.title)
        self.empty_hint.grid_remove()
        self._window = None
        self._show_position(start_index)
        self._show_state("stopped")

    def set_voices(self, voices: list[dict[str, Any]], selected_id: str | None) -> None:
        self._voice_by_label = {describe_voice(v): v["voice_id"] for v in voices}
        labels = list(self._voice_by_label) + [_ADD_VOICE]
        self.voice_box.configure(values=labels)
        chosen = next((label for label, vid in self._voice_by_label.items() if vid == selected_id), None)
        self.voice_box.set(chosen or (labels[0] if self._voice_by_label else ""))

    def set_speed_label(self, speed: float) -> None:
        self.speed_buttons.set(f"{speed}x")

    def _voice_chosen(self, label: str) -> None:
        if label == _ADD_VOICE:
            self.ctx.app.open_voices()
            self.set_voices(self.ctx.app.voices, self.ctx.app.current_voice_id)
            return
        self.ctx.app.select_voice(self._voice_by_label[label])

    def _speed_chosen(self, label: str) -> None:
        self.ctx.reader.set_speed(float(label.rstrip("x")))

    def _pick_book(self) -> None:
        BookPickerDialog(self, self.ctx, lambda b: self.ctx.app.open_in_reader(b["id"], b["title"]))

    # -- rendering -----------------------------------------------------------------------------------------

    def _render_window(self, center: int) -> None:
        reader = self.ctx.reader
        total = reader.total
        lo, hi = max(0, center - WINDOW_RADIUS), min(total - 1, center + WINDOW_RADIUS)
        window = self._window
        if window:
            far_from_start = center - window[0] >= 8 or window[0] == 0
            far_from_end = window[1] - center >= 8 or window[1] == total - 1
            if window[0] <= center <= window[1] and far_from_start and far_from_end:
                return  # still comfortably inside the rendered window
        self._window = (lo, hi)
        assert reader.book is not None
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for i in range(lo, hi + 1):
            self.text.insert("end", reader.book.sentences[i]["text_content"], f"s{i}")
            self.text.insert("end", "\n")
        self.text.configure(state="disabled")

    def _show_position(self, index: int) -> None:
        reader = self.ctx.reader
        if not reader.book or not reader.total:
            return
        index = min(max(index, 0), reader.total - 1)
        self._render_window(index)
        self.text.tag_remove("current", "1.0", "end")
        self.text.tag_remove("done", "1.0", "end")
        ranges = self.text.tag_ranges(f"s{index}")
        if ranges:
            self.text.tag_add("current", ranges[0], ranges[1])
            self.text.tag_add("done", "1.0", ranges[0])
            self.text.see(ranges[0])
        self.position_label.configure(text=f"Câu {format_number(index + 1)} / {format_number(reader.total)}"
                                           f"   ({(index + 1) / reader.total * 100:.1f}%)")
        self.progress.set((index + 1) / reader.total)
        self.jump_entry.delete(0, "end")
        self.jump_entry.insert(0, str(index + 1))
        self.note_btn.configure(state="disabled")

    def _show_state(self, state: str) -> None:
        self._state = state
        self.play_btn.configure(text="⏸" if state == "playing" else "▶")
        self._tick_status(reschedule=False)
        if state == "finished":
            self.ctx.app.toast("Đã đọc xong. Bấm ▶ để đọc lại câu cuối, hoặc ⏮ để về đầu.")

    def _tick_status(self, reschedule: bool = True) -> None:
        buffered, prefetch, latency = self.ctx.reader.engine_status
        text = _STATE_TEXT.get(self._state, "")
        if self._state in ("playing", "paused"):
            text += f" · bộ đệm {buffered}/{prefetch} · độ trễ {latency:.0f} ms"
        self.status_label.configure(text=text)
        if reschedule:
            self.after(500, self._tick_status)

    # -- actions -----------------------------------------------------------------------------------------------

    def _toggle(self) -> None:
        if not self.ctx.reader.book:
            self.ctx.app.toast("Chưa chọn tài liệu.")
            return
        self.ctx.reader.toggle()

    def _jump_from_entry(self) -> None:
        try:
            self.ctx.reader.jump(int(self.jump_entry.get()) - 1)
        except ValueError:
            self.ctx.app.toast("Số câu không hợp lệ.")

    def _on_text_click(self, event: tk.Event) -> None:
        if self.text.tag_ranges("sel"):
            self.note_btn.configure(state="normal")
            return
        self.note_btn.configure(state="disabled")
        sentence = self._sentence_at(self.text.index(f"@{event.x},{event.y}"))
        if sentence is not None:
            self.ctx.reader.jump(sentence)

    def _sentence_at(self, text_index: str) -> int | None:
        for tag in self.text.tag_names(text_index):
            if tag.startswith("s") and tag[1:].isdigit():
                return int(tag[1:])
        return None

    def _selection(self) -> tuple[int, int, int, str] | None:
        """(sentence_index, start_offset, end_offset, excerpt) if the selection lies in one sentence."""
        if not self.text.tag_ranges("sel"):
            return None
        first, last = str(self.text.index("sel.first")), str(self.text.index("sel.last"))
        sentence = self._sentence_at(first)
        if sentence is None:
            return None
        raw = self.text._textbox  # CTkTextbox hides `compare`
        if raw.compare(last, ">", f"s{sentence}.last"):
            return None
        start = len(self.text.get(f"s{sentence}.first", first))
        excerpt = self.text.get(first, last)
        return sentence, start, start + len(excerpt), excerpt

    def _note(self) -> None:
        book = self.ctx.reader.book
        selection = self._selection()
        if not book:
            return
        if selection is None:
            self.ctx.app.toast("Hãy chọn một đoạn nằm trong cùng một câu.")
            return
        sentence, start, end, excerpt = selection
        NoteDialog(self, self.ctx, book.book_id, sentence, start, end, excerpt,
                   on_saved=lambda: self.ctx.app.toast("Đã lưu ghi chú."))
