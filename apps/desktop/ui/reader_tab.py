"""S03 – Phòng Đọc: karaoke text view, transport controls, speed, jump, notes."""

from __future__ import annotations

import tkinter as tk
from typing import Any

import customtkinter as ctk

import config
from player.chapters import chapter_at
from ui import theme
from ui.common import AppContext, error_text
from ui.dialogs import (
    AmbientDialog,
    BookPickerDialog,
    ChapterListDialog,
    NoteDialog,
    SleepTimerDialog,
)
from ui.viewmodels import EMOTIONS, describe_voice, format_number

WINDOW_RADIUS = 60  # sentences rendered on each side of the current one
_ADD_VOICE = "+ Thêm giọng mới…"
_ONE_VOICE = "Một giọng (không phân vai)"
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
        self.after(250, self._tick_sleep)

    # -- layout -------------------------------------------------------------------------------

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(title_box, text="ĐANG ĐỌC", anchor="w", text_color=theme.ACCENT,
                     font=theme.font(11, "bold")).pack(anchor="w")
        self.title_label = ctk.CTkLabel(title_box, text="Chưa chọn tài liệu", anchor="w",
                                        font=theme.font(24, "bold", serif=True))
        self.title_label.pack(anchor="w")
        self.toc_btn = ctk.CTkButton(header, text="☰ Mục lục", width=100, command=self._open_toc, **theme.SECONDARY)
        self.toc_btn.grid(row=0, column=1, padx=(0, 6))
        self.toc_btn.grid_remove()  # shown only for books with more than one chapter
        ctk.CTkButton(header, text="Đổi tài liệu", width=110, command=self._pick_book,
                      **theme.SECONDARY).grid(row=0, column=2, padx=6)
        ctk.CTkLabel(header, text="Giọng", text_color=theme.TEXT_2).grid(row=0, column=3, padx=(10, 4))
        self.voice_box = ctk.CTkComboBox(header, values=[""], width=260, state="readonly", command=self._voice_chosen)
        self.voice_box.grid(row=0, column=4)
        ctk.CTkLabel(header, text="Giọng nhân vật", text_color=theme.TEXT_2).grid(row=1, column=3, padx=(10, 4), pady=(6, 0))
        self.character_box = ctk.CTkComboBox(header, values=[_ONE_VOICE], width=260, state="readonly",
                                             command=self._character_chosen)
        self.character_box.set(_ONE_VOICE)
        self.character_box.grid(row=1, column=4, pady=(6, 0))

        self.text = ctk.CTkTextbox(self, wrap="word", font=theme.font(17, serif=True), spacing3=8, border_spacing=12)
        self.text.grid(row=1, column=0, sticky="nsew", pady=4)
        self._apply_tags()
        self.text.bind("<ButtonRelease-1>", self._on_text_click)
        self.text.configure(state="disabled")
        self.empty_hint = ctk.CTkLabel(self, text="Chưa chọn tài liệu. Bấm “Đổi tài liệu” hoặc mở Thư Viện.",
                                       text_color=theme.MUTED)
        self.empty_hint.grid(row=1, column=0)

        note_row = ctk.CTkFrame(self, fg_color="transparent")
        note_row.grid(row=2, column=0, sticky="e", pady=(2, 6))
        self.tag_bar = ctk.CTkFrame(note_row, fg_color=theme.ACCENT_SOFT, corner_radius=10)
        ctk.CTkLabel(self.tag_bar, text="⭐ Đã lưu đoạn này. Gắn nhãn:", text_color=theme.ACCENT,
                     font=theme.font(12, "bold")).pack(side="left", padx=(12, 6), pady=6)
        for value, label in EMOTIONS:
            ctk.CTkButton(self.tag_bar, text=label, height=28, width=60, command=lambda v=value: self._tag_saved_quote(v),
                          **theme.SECONDARY).pack(side="left", padx=3)
        ctk.CTkButton(self.tag_bar, text="Xem", width=44, height=28, command=self._open_saved_quotes, **theme.GHOST).pack(
            side="left", padx=(3, 8))
        self.bookmark_btn = ctk.CTkButton(note_row, text="⭐ Đánh dấu đoạn này (B)", command=self._bookmark, **theme.SECONDARY)
        self.bookmark_btn.pack(side="left", padx=(8, 6))
        self.note_btn = ctk.CTkButton(note_row, text="📝 Trích đoạn đã chọn", state="disabled", command=self._note,
                                      **theme.SECONDARY)
        self.note_btn.pack(side="left")
        self._saved_quote: dict[str, Any] | None = None
        self._tag_job: str | None = None

        dock = ctk.CTkFrame(self, border_width=1, border_color=theme.BORDER_STRONG, corner_radius=16)
        dock.grid(row=3, column=0, sticky="ew")
        dock.columnconfigure(0, weight=1)
        self.progress = ctk.CTkProgressBar(dock, height=6)
        self.progress.set(0)
        self.progress.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 0))
        self.position_label = ctk.CTkLabel(dock, text="Câu 0 / 0", anchor="w", text_color=theme.TEXT_2,
                                           font=theme.font(12))
        self.position_label.grid(row=1, column=0, sticky="w", padx=20)

        controls = ctk.CTkFrame(dock, fg_color="transparent")
        controls.grid(row=2, column=0, pady=4)
        reader = self.ctx.reader
        for text, command in (
            ("⏮", lambda: reader.jump(0)), ("‹ Câu trước", reader.previous),
        ):
            ctk.CTkButton(controls, text=text, width=100 if "Câu" in text else 46, height=40,
                          command=command, **theme.SECONDARY).pack(side="left", padx=4)
        self.play_btn = ctk.CTkButton(controls, text="▶", width=60, height=60, corner_radius=30,
                                      font=theme.font(22), command=self._toggle)
        self.play_btn.pack(side="left", padx=8)
        for text, command in (
            ("Câu sau ›", reader.next), ("⏭", lambda: reader.jump(max(reader.total - 1, 0))),
        ):
            ctk.CTkButton(controls, text=text, width=100 if "Câu" in text else 46, height=40,
                          command=command, **theme.SECONDARY).pack(side="left", padx=4)

        options = ctk.CTkFrame(dock, fg_color="transparent")
        options.grid(row=3, column=0, pady=2)
        ctk.CTkLabel(options, text="Tốc độ", text_color=theme.TEXT_2).pack(side="left", padx=(0, 8))
        self.speed_buttons = ctk.CTkSegmentedButton(
            options, values=[f"{s}x" for s in config.SPEED_LEVELS], command=self._speed_chosen)
        self.speed_buttons.set("1.0x")
        self.speed_buttons.pack(side="left")
        self.sleep_btn = ctk.CTkButton(options, text="⏲ Hẹn giờ", width=110, command=self._open_sleep, **theme.SECONDARY)
        self.sleep_btn.pack(side="left", padx=(18, 0))
        self.ambient_btn = ctk.CTkButton(options, text="🎵 Nhạc nền", width=120, command=self._open_ambient, **theme.SECONDARY)
        self.ambient_btn.pack(side="left", padx=(8, 0))
        ctk.CTkLabel(options, text="     Nhảy tới câu", text_color=theme.TEXT_2).pack(side="left")
        self.jump_entry = ctk.CTkEntry(options, width=70)
        self.jump_entry.pack(side="left", padx=6)
        self.jump_entry.bind("<Return>", lambda _e: self._jump_from_entry())
        ctk.CTkButton(options, text="Đi", width=44, command=self._jump_from_entry, **theme.SECONDARY).pack(side="left")

        self.status_label = ctk.CTkLabel(dock, text="", anchor="center", text_color=theme.MUTED, font=theme.font(12))
        self.status_label.grid(row=4, column=0, sticky="ew", padx=20, pady=(2, 12))

    def _apply_tags(self) -> None:
        """Tk text tags cannot take light/dark pairs, so they are set for the current appearance."""
        self.text.tag_config("current", background=theme.mode_color(theme.ACCENT_SOFT),
                             foreground=theme.mode_color(theme.TEXT))
        self.text.tag_config("done", foreground=theme.mode_color(theme.MUTED))

    def refresh_theme(self) -> None:
        self._apply_tags()

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
        if len(book.chapters) > 1:
            self.toc_btn.grid()
        else:
            self.toc_btn.grid_remove()
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
        self.character_box.configure(values=[_ONE_VOICE] + list(self._voice_by_label))
        self.show_character_voice()

    def show_character_voice(self) -> None:
        """Show the saved character voice (or "none") in its box."""
        current = self.ctx.app.settings.get("character_voice") or ""
        label = next((lbl for lbl, vid in self._voice_by_label.items() if vid == current), None)
        self.character_box.set(label or _ONE_VOICE)

    def _character_chosen(self, label: str) -> None:
        voice = self._voice_by_label.get(label, "")
        self.ctx.reader.set_character_voice(voice)  # takes effect at once, before the server has answered
        settings = {**{k: self.ctx.app.settings[k] for k in ("prefetch_count", "default_speed", "default_voice", "daily_char_limit")},
                    "character_voice": voice}

        def saved(result: dict[str, Any]) -> None:
            self.ctx.app.apply_settings(result)
            self.ctx.app.toast("Đã bật đọc phân vai: lời thoại trong ngoặc kép đọc bằng giọng nhân vật." if voice
                               else "Đã tắt đọc phân vai.")

        self.ctx.ui.run_in_thread(lambda: self.ctx.api.update_settings(settings), saved,
                                  lambda exc: self.ctx.app.show_error(error_text(exc)))

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
        chapter = chapter_at(reader.book.chapters, index) if len(reader.book.chapters) > 1 else None
        where = f"  ·  {chapter['title'][:70]}" if chapter else ""
        self.position_label.configure(text=f"Câu {format_number(index + 1)} / {format_number(reader.total)}"
                                           f"   ({(index + 1) / reader.total * 100:.1f}%){where}")
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

    def _tick_sleep(self) -> None:
        self.refresh_sleep()
        self.after(250, self._tick_sleep)

    def refresh_sleep(self) -> None:
        """Run the sleep timer one step and show its state on the button."""
        active = self.ctx.reader.sleep.active
        label = self.ctx.reader.sleep_tick()
        self.sleep_btn.configure(text=f"⏲ {label}", **(theme.ACCENT_SOFT_BUTTON if active else theme.SECONDARY))

    def _open_toc(self) -> None:
        book = self.ctx.reader.book
        if not book or len(book.chapters) < 2:
            return
        current = chapter_at(book.chapters, self.ctx.reader.index)
        ChapterListDialog(
            self, self.ctx, book.chapters, current["chapter_index"] if current else None,
            on_pick=lambda chapter: self.ctx.reader.jump(chapter["start_sentence_index"], autoplay=True))

    def refresh_ambient(self) -> None:
        """Highlight the button while a background sound is chosen."""
        on = bool(self.ctx.app.settings.get("ambient_track"))
        self.ambient_btn.configure(**(theme.ACCENT_SOFT_BUTTON if on else theme.SECONDARY))

    def _open_ambient(self) -> None:
        AmbientDialog(self, self.ctx, on_changed=self.refresh_ambient)

    def _open_sleep(self) -> None:
        if not self.ctx.reader.book:
            self.ctx.app.toast("Chưa chọn tài liệu.")
            return
        SleepTimerDialog(self, self.ctx, on_change=self.refresh_sleep)

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
                   on_saved=lambda: self.ctx.app.toast("Đã lưu trích dẫn."))

    # -- one-tap favourite quote ---------------------------------------------------------------------------

    def _bookmark(self) -> None:
        """Save the sentence being read as a favourite quote; the feeling buttons then appear for a few seconds."""
        book = self.ctx.reader.book
        if not book:
            self.ctx.app.toast("Chưa chọn tài liệu.")
            return
        index, voice = self.ctx.reader.index, self.ctx.app.current_voice_id
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.create_note(book.book_id, index, voice=voice), self._quote_saved,
            lambda exc: self.ctx.app.show_error(error_text(exc)))

    def _quote_saved(self, note: dict[str, Any]) -> None:
        self._saved_quote = note
        self.tag_bar.pack(side="left", before=self.bookmark_btn)
        if self._tag_job:
            self.after_cancel(self._tag_job)
        self._tag_job = self.after(8000, self._hide_tag_bar)

    def _hide_tag_bar(self) -> None:
        self._tag_job = None
        self._saved_quote = None
        self.tag_bar.pack_forget()

    def _tag_saved_quote(self, tag: str) -> None:
        note = self._saved_quote
        if not note:
            return
        self.ctx.ui.run_in_thread(
            lambda: self.ctx.api.update_note(note["id"], emotion_tag=tag),
            lambda saved: (self.ctx.app.toast(f'Đã gắn nhãn "{dict(EMOTIONS)[tag]}".'), self._quote_saved(saved)),
            lambda exc: self.ctx.app.show_error(error_text(exc)))

    def _open_saved_quotes(self) -> None:
        book = self.ctx.reader.book
        self._hide_tag_bar()
        if book:
            self.ctx.app.show_quotes_for(book.book_id)
