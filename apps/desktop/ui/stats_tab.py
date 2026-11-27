"""S08 – Thống Kê: KPI tiles + Matplotlib charts embedded with FigureCanvasTkAgg."""

from __future__ import annotations

import tkinter as tk
from typing import Any

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ui import theme
from ui.common import AppContext, error_text
from ui.viewmodels import format_minutes, format_number

_RANGES = {"7 ngày": 7, "30 ngày": 30, "Tất cả": 365}
_WEEKDAYS = ("T2", "T3", "T4", "T5", "T6", "T7", "CN")


class StatsTab(ctk.CTkFrame):
    def __init__(self, master: tk.Misc, ctx: AppContext):
        super().__init__(master, fg_color="transparent")
        self.ctx = ctx
        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(titles, text="Thống kê", anchor="w", font=theme.font(26, "bold")).pack(anchor="w")
        ctk.CTkLabel(titles, text="Thói quen nghe của bạn theo thời gian.", anchor="w",
                     text_color=theme.MUTED).pack(anchor="w")
        self.range_buttons = ctk.CTkSegmentedButton(header, values=list(_RANGES), command=lambda _v: self.refresh())
        self.range_buttons.set("7 ngày")
        self.range_buttons.grid(row=0, column=1, sticky="e")

        self.tiles_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.tiles_frame.grid(row=1, column=0, sticky="ew")
        self.tile_labels: dict[str, ctk.CTkLabel] = {}
        for col, (key, title) in enumerate((
            ("time", "Tổng thời gian"), ("words", "Tổng số từ"),
            ("speed", "Tốc độ TB"), ("success", "Tỷ lệ thành công"),
        )):
            self.tiles_frame.columnconfigure(col, weight=1)
            tile = ctk.CTkFrame(self.tiles_frame, border_width=1, border_color=theme.BORDER, corner_radius=16)
            tile.grid(row=0, column=col, padx=(0 if col == 0 else 8, 0), sticky="ew")
            ctk.CTkLabel(tile, text=title, anchor="w", text_color=theme.MUTED, font=theme.font(12)).pack(
                anchor="w", padx=16, pady=(12, 0))
            value = ctk.CTkLabel(tile, text="—", anchor="w", font=theme.font(24, "bold"))
            value.pack(anchor="w", padx=16, pady=(0, 12))
            self.tile_labels[key] = value

        self.latency_label = ctk.CTkLabel(self, text="Độ trễ API: —", anchor="w", text_color=theme.MUTED,
                                          font=theme.font(12))
        self.latency_label.grid(row=2, column=0, sticky="w", pady=8)
        self.message = ctk.CTkLabel(self, text="", text_color=theme.TEXT_2)
        self.message.grid(row=3, column=0)

        self.figure = Figure(figsize=(9, 5), dpi=100, layout="constrained")
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().grid(row=4, column=0, sticky="nsew", pady=(0, 6))
        self._last: tuple[list[dict[str, Any]], list[dict[str, Any]]] | None = None

    def refresh(self) -> None:
        days = _RANGES[self.range_buttons.get()]
        self.message.configure(text="Đang tải…", text_color=theme.TEXT_2)

        def work() -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
            return (self.ctx.api.analytics_daily(days), self.ctx.api.analytics_metrics(days),
                    self.ctx.api.analytics_voices(days))

        self.ctx.ui.run_in_thread(work, self._loaded, self._failed)

    def _failed(self, exc: Exception) -> None:
        self.message.configure(text=error_text(exc), text_color=theme.DANGER)

    def _loaded(self, result: tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]) -> None:
        daily, metrics, voices = result
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
        self._last = (daily, voices)
        self._render_charts(daily, voices)

    def _render_charts(self, daily: list[dict[str, Any]], voices: list[dict[str, Any]]) -> None:
        ink, muted = theme.mode_color(theme.TEXT), theme.mode_color(theme.MUTED)
        surface, grid = theme.mode_color(theme.BG), theme.mode_color(theme.BORDER)  # charts sit on the page background
        labels = [self._day_label(d["date"], len(daily)) for d in daily]
        self.figure.clear()
        self.figure.set_facecolor(surface)
        spec = self.figure.add_gridspec(2, 2)
        top = self.figure.add_subplot(spec[0, :])
        bottom = self.figure.add_subplot(spec[1, 0])
        pie = self.figure.add_subplot(spec[1, 1])
        top.bar(labels, [d["minutes"] for d in daily], color=theme.mode_color(theme.CHARTS[0]), width=0.6)
        bottom.bar(labels, [d["words"] for d in daily], color=theme.mode_color(theme.CHARTS[1]), width=0.6)
        for axis, title in ((top, "Phút nghe theo ngày"), (bottom, "Số từ theo ngày"), (pie, "Thời gian nghe theo giọng")):
            axis.set_facecolor(surface)
            axis.set_title(title, color=ink, fontsize=11, fontweight="bold", loc="left")
        for axis in (top, bottom):
            axis.tick_params(axis="x", labelrotation=45 if len(daily) > 10 else 0, labelsize=8, colors=muted)
            axis.tick_params(axis="y", labelsize=8, colors=muted)
            axis.grid(axis="y", color=grid, linewidth=0.8)
            axis.set_axisbelow(True)
            for side in ("top", "right", "left"):
                axis.spines[side].set_visible(False)
            axis.spines["bottom"].set_color(grid)
            if len(daily) > 31:
                step = max(len(daily) // 12, 1)
                positions = list(range(0, len(daily), step))
                axis.set_xticks(positions, labels=[labels[i] for i in positions])
        shares = [v for v in voices if v["minutes"] > 0]
        if shares:
            colors = [theme.mode_color(theme.CHARTS[i % len(theme.CHARTS)]) for i in range(len(shares))]
            _, texts, autotexts = pie.pie(
                [v["minutes"] for v in shares], labels=[v["display_name"] for v in shares], autopct="%1.0f%%",
                colors=colors, startangle=90, counterclock=False, wedgeprops={"edgecolor": surface, "linewidth": 2})
            for text in texts:
                text.set_color(ink)
                text.set_fontsize(8)
            for text in autotexts:
                text.set_color("#ffffff")
                text.set_fontsize(8)
        else:
            pie.text(0.5, 0.5, "Chưa có dữ liệu", ha="center", va="center", color=muted, transform=pie.transAxes)
            pie.set_axis_off()
        self.canvas.draw_idle()

    @staticmethod
    def _day_label(iso_date: str, count: int) -> str:
        from datetime import date

        parsed = date.fromisoformat(iso_date)
        return _WEEKDAYS[parsed.weekday()] if count <= 7 else parsed.strftime("%d/%m")
