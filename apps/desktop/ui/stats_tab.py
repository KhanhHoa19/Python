"""S08 – Thống Kê: KPI tiles + Matplotlib charts embedded with FigureCanvasTkAgg."""

from __future__ import annotations

import tkinter as tk
from typing import Any

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ui.common import AppContext, error_text
from ui.viewmodels import format_minutes, format_number

_RANGES = {"7 ngày": 7, "30 ngày": 30, "Tất cả": 365}
_WEEKDAYS = ("T2", "T3", "T4", "T5", "T6", "T7", "CN")
_BAR_COLOR = "#3b8ed0"


class StatsTab(ctk.CTkFrame):
    def __init__(self, master: tk.Misc, ctx: AppContext):
        super().__init__(master, fg_color="transparent")
        self.ctx = ctx
        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)

        self.range_buttons = ctk.CTkSegmentedButton(self, values=list(_RANGES), command=lambda _v: self.refresh())
        self.range_buttons.set("7 ngày")
        self.range_buttons.grid(row=0, column=0, pady=(10, 6))

        self.tiles_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.tiles_frame.grid(row=1, column=0, sticky="ew", padx=12)
        self.tile_labels: dict[str, ctk.CTkLabel] = {}
        for col, (key, title) in enumerate((
            ("time", "Tổng thời gian"), ("words", "Tổng số từ"),
            ("speed", "Tốc độ TB"), ("success", "Tỷ lệ thành công"),
        )):
            self.tiles_frame.columnconfigure(col, weight=1)
            tile = ctk.CTkFrame(self.tiles_frame)
            tile.grid(row=0, column=col, padx=4, sticky="ew")
            ctk.CTkLabel(tile, text=title, text_color=("gray35", "gray65")).pack(pady=(8, 0))
            value = ctk.CTkLabel(tile, text="—", font=ctk.CTkFont(size=22, weight="bold"))
            value.pack(pady=(0, 8))
            self.tile_labels[key] = value

        self.latency_label = ctk.CTkLabel(self, text="Độ trễ API: —")
        self.latency_label.grid(row=2, column=0, pady=6)
        self.message = ctk.CTkLabel(self, text="")
        self.message.grid(row=3, column=0)

        self.figure = Figure(figsize=(9, 5), dpi=100, layout="constrained")
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().grid(row=4, column=0, sticky="nsew", padx=12, pady=(0, 10))

    def refresh(self) -> None:
        days = _RANGES[self.range_buttons.get()]
        self.message.configure(text="Đang tải…", text_color=("gray20", "gray80"))

        def work() -> tuple[list[dict[str, Any]], dict[str, Any]]:
            return self.ctx.api.analytics_daily(days), self.ctx.api.analytics_metrics(days)

        self.ctx.ui.run_in_thread(work, self._loaded, self._failed)

    def _failed(self, exc: Exception) -> None:
        self.message.configure(text=error_text(exc), text_color="#d64545")

    def _loaded(self, result: tuple[list[dict[str, Any]], dict[str, Any]]) -> None:
        daily, metrics = result
        total_minutes = sum(d["minutes"] for d in daily)
        total_words = sum(d["words"] for d in daily)
        if not any(d["sessions"] for d in daily):
            self.message.configure(text="Chưa có dữ liệu đọc. Hãy nghe một vài câu rồi quay lại.")
        else:
            self.message.configure(text="")
        self.tile_labels["time"].configure(text=format_minutes(total_minutes))
        self.tile_labels["words"].configure(text=format_number(total_words))
        self.tile_labels["speed"].configure(text=f"{metrics['words_per_minute']:.0f} từ/ph")
        self.tile_labels["success"].configure(text=f"{metrics['success_rate']:.1f}%" if metrics["total_calls"] else "—")
        self.latency_label.configure(
            text=f"Độ trễ API (ms): trung bình {metrics['avg_latency_ms']:.0f} · P95 {metrics['p95_latency_ms']:.0f}"
                 f" · lớn nhất {metrics['max_latency_ms']:.0f}" if metrics["total_calls"] else "Độ trễ API: chưa có dữ liệu")
        self._render_charts(daily)

    def _render_charts(self, daily: list[dict[str, Any]]) -> None:
        labels = [self._day_label(d["date"], len(daily)) for d in daily]
        self.figure.clear()
        top, bottom = self.figure.subplots(2, 1)
        top.bar(labels, [d["minutes"] for d in daily], color=_BAR_COLOR)
        top.set_title("Phút nghe theo ngày")
        bottom.bar(labels, [d["words"] for d in daily], color="#2e9d57")
        bottom.set_title("Số từ theo ngày")
        for axis in (top, bottom):
            axis.tick_params(axis="x", labelrotation=45 if len(daily) > 10 else 0, labelsize=8)
            if len(daily) > 31:
                step = max(len(daily) // 12, 1)
                positions = list(range(0, len(daily), step))
                axis.set_xticks(positions, labels=[labels[i] for i in positions])
        self.canvas.draw_idle()

    @staticmethod
    def _day_label(iso_date: str, count: int) -> str:
        from datetime import date

        parsed = date.fromisoformat(iso_date)
        return _WEEKDAYS[parsed.weekday()] if count <= 7 else parsed.strftime("%d/%m")
