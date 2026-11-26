"""Shared UI plumbing: application context and a modal dialog base class."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import customtkinter as ctk

from api_client import ApiClient, ApiError
from player.audio_output import AudioOutput
from player.controller import ReaderController
from ui.dispatcher import UiDispatcher


@dataclass
class AppContext:
    """Everything a screen needs. `app` exposes navigation and shared state (see ui/app.py)."""

    api: ApiClient
    ui: UiDispatcher
    reader: ReaderController
    output: AudioOutput
    app: Any


def error_text(exc: Exception) -> str:
    return exc.message if isinstance(exc, ApiError) else f"Lỗi không mong muốn: {exc}"


class ModalDialog(ctk.CTkToplevel):
    """Centered-on-parent modal window that is safe against late background callbacks."""

    def __init__(self, master: tk.Misc, title: str, width: int, height: int):
        super().__init__(master)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.minsize(width, height)
        self.transient(master.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(150, self._grab)  # grabbing before the window is mapped fails on Linux

    def _grab(self) -> None:
        try:
            self.grab_set()
            self.focus_set()
        except tk.TclError:
            pass

    def close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()

    def guard(self, func: Callable[..., Any]) -> Callable[..., None]:
        """Wrap a callback so it is ignored if the dialog was closed meanwhile."""

        def wrapped(*args: Any) -> None:
            if self.winfo_exists():
                func(*args)

        return wrapped
