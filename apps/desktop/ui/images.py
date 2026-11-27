"""Book cover thumbnails: a coloured tile with initials at once, replaced by the real image when it arrives."""

from __future__ import annotations

import io
import tkinter as tk
from typing import Any

import customtkinter as ctk
from PIL import Image

from ui import theme
from ui.viewmodels import cover_color, cover_initials


class CoverCache:
    """Downloads covers on a worker thread (never in the UI thread) and keeps the bytes for the next screen."""

    def __init__(self) -> None:
        self._bytes: dict[str, bytes] = {}

    def has(self, url: str) -> bool:
        return url in self._bytes

    def image(self, url: str, size: tuple[int, int]) -> Any:
        """A CTkImage of the cached bytes at `size`."""
        picture = Image.open(io.BytesIO(self._bytes[url])).convert("RGB")
        return ctk.CTkImage(light_image=picture, dark_image=picture, size=size)

    def fetch(self, ctx: Any, url: str, done: Any) -> None:
        """Make sure `url` is cached, then call `done()` on the UI thread. A failed download is silently ignored."""
        if self.has(url):
            done()
            return

        def work() -> bytes:
            return ctx.api.cover_bytes(url)

        def stored(data: bytes) -> None:
            self._bytes[url] = data
            done()

        ctx.ui.run_in_thread(work, stored, lambda _exc: None)


class CoverView(ctk.CTkFrame):
    """A fixed-size cover: coloured placeholder first, then the book's image (if it has one)."""

    def __init__(self, master: tk.Misc, ctx: Any, title: str, url: str | None, size: tuple[int, int] = (84, 112)):
        super().__init__(master, width=size[0], height=size[1], corner_radius=10, fg_color=cover_color(title))
        self.grid_propagate(False)
        self.pack_propagate(False)
        self.size = size
        self.label = ctk.CTkLabel(self, text=cover_initials(title), text_color="#ffffff",
                                  font=theme.font(max(12, size[0] // 3), "bold", serif=True))
        self.label.place(relx=0.5, rely=0.5, anchor="center")
        if url:
            ctx.covers.fetch(ctx, url, lambda: self._show(ctx, url))

    def _show(self, ctx: Any, url: str) -> None:
        if not self.winfo_exists():  # the list was redrawn while the image was downloading
            return
        self.label.destroy()  # a fresh label sized to the image (re-placing the text label left the picture cropped)
        self.label = ctk.CTkLabel(self, text="", image=ctx.covers.image(url, self.size), width=self.size[0],
                                  height=self.size[1], fg_color="transparent", corner_radius=0)
        self.label.pack()
