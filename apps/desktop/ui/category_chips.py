"""The topic tags of the library (Trinh thám, Khoa học…): click one to filter, click it again to clear."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from ui import theme

_GAP = 6


class CategoryChips(ctk.CTkFrame):
    """A row of tag buttons that wraps onto more lines when the window is narrow."""

    def __init__(self, master: tk.Misc, on_pick: Callable[[str | None], None]):
        super().__init__(master, fg_color="transparent")
        self._on_pick = on_pick
        self._buttons: list[ctk.CTkButton] = []
        self._width = 0
        self.bind("<Configure>", self._on_resize)

    def set_categories(self, categories: list[dict[str, Any]], selected: str | None) -> None:
        for button in self._buttons:
            button.destroy()
        entries: list[tuple[str, str | None]] = [("Tất cả", None)] + [(c["name"], c["slug"]) for c in categories]
        self._buttons = []
        for label, slug in entries:
            active = slug == selected
            self._buttons.append(ctk.CTkButton(
                self, text=label, height=28, corner_radius=14, font=theme.font(12, "bold" if active else "normal"),
                command=lambda s=slug: self._on_pick(s),
                **({"fg_color": theme.ACCENT_SOFT, "hover_color": theme.ACCENT_SOFT, "text_color": theme.ACCENT,
                    "border_width": 1, "border_color": theme.ACCENT} if active else
                   {**theme.SECONDARY, "border_width": 1, "border_color": theme.BORDER_STRONG}),
            ))
        self._reflow()

    def _on_resize(self, event: tk.Event) -> None:
        if abs(event.width - self._width) > 4:
            self._width = event.width
            self._reflow()

    def _reflow(self) -> None:
        """Place the buttons left to right, starting a new line when the next one would not fit."""
        x = row = column = 0
        width = max(self._width, 300)
        for button in self._buttons:
            need = button.winfo_reqwidth() + _GAP
            if x + need > width and column:
                row, column, x = row + 1, 0, 0
            button.grid(row=row, column=column, padx=(0, _GAP), pady=(0, _GAP), sticky="w")
            x += need
            column += 1
