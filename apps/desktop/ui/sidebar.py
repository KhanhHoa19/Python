"""Left navigation: brand, screens, tools, appearance. Add new screens with `SidebarTabs.add(name, icon)`."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from ui import theme

_NAV_WIDTH = 232


class SidebarTabs(ctk.CTkFrame):
    """Drop-in replacement for CTkTabview: `add(name)` returns the screen's frame, `set`/`get` switch it."""

    def __init__(self, master: tk.Misc, command: Callable[[], None] | None = None):
        super().__init__(master, fg_color="transparent")
        self._command = command
        self._frames: dict[str, ctk.CTkFrame] = {}
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._icons: dict[str, str] = {}
        self._current: str | None = None
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.nav = ctk.CTkFrame(self, width=_NAV_WIDTH, corner_radius=0, fg_color=theme.SURFACE)
        self.nav.grid(row=0, column=0, sticky="ns")
        self.nav.grid_propagate(False)
        self.nav.columnconfigure(0, weight=1)
        self.nav.rowconfigure(5, weight=1)

        brand = ctk.CTkFrame(self.nav, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=16, pady=(18, 12))
        ctk.CTkLabel(brand, text="🎧", width=38, height=38, corner_radius=11, fg_color=theme.ACCENT,
                     text_color=theme.ACCENT_INK, font=theme.font(18)).pack(side="left")
        ctk.CTkLabel(brand, text="Audiobook ", font=theme.font(16, "bold")).pack(side="left", padx=(10, 0))
        ctk.CTkLabel(brand, text="TTS", font=theme.font(16, "bold"), text_color=theme.ACCENT).pack(side="left")

        self.account = ctk.CTkFrame(self.nav, fg_color=theme.SURFACE_2, corner_radius=12)
        self.account.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        self.avatar = ctk.CTkLabel(self.account, text="?", width=36, height=36, corner_radius=18,
                                   fg_color=theme.ACCENT_SOFT, text_color=theme.ACCENT, font=theme.font(14, "bold"))
        self.avatar.pack(side="left", padx=(10, 8), pady=8)
        names = ctk.CTkFrame(self.account, fg_color="transparent")
        names.pack(side="left", fill="x", expand=True, pady=6)
        self.account_name = ctk.CTkLabel(names, text="", anchor="w", font=theme.font(13, "bold"))
        self.account_name.pack(fill="x")
        self.account_role = ctk.CTkLabel(names, text="", anchor="w", font=theme.font(10, "bold"), text_color=theme.MUTED)
        self.account_role.pack(fill="x")

        self.items = ctk.CTkFrame(self.nav, fg_color="transparent")
        self.items.grid(row=2, column=0, sticky="new", padx=12)
        self.items.columnconfigure(0, weight=1)

        self.footer = ctk.CTkFrame(self.nav, fg_color="transparent")
        self.footer.grid(row=6, column=0, sticky="sew", padx=12, pady=(0, 10))
        self.footer.columnconfigure(0, weight=1)
        ctk.CTkLabel(self.footer, text="CÔNG CỤ", anchor="w", text_color=theme.MUTED,
                     font=theme.font(10, "bold")).grid(row=0, column=0, sticky="ew", padx=12, pady=(0, 4))
        self._footer_rows = 1

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(1, weight=1)  # row 0: banner, row 1: screens, row 2: toast

    def set_account(self, user: dict) -> None:
        """Show who is signed in (avatar letter, name, role badge)."""
        from ui.viewmodels import avatar_letter

        self.avatar.configure(text=avatar_letter(user))
        self.account_name.configure(text=user.get("full_name") or user.get("username", ""))
        is_admin = user.get("role") == "admin"
        self.account_role.configure(text="ADMIN" if is_admin else "MEMBER",
                                    text_color=theme.ACCENT if is_admin else theme.MUTED)

    # -- CTkTabview-compatible API ------------------------------------------------------------------

    def add(self, name: str, icon: str = "•") -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.content, fg_color="transparent", corner_radius=0)
        frame.grid(row=1, column=0, sticky="nsew")
        frame.grid_remove()
        self._frames[name] = frame
        self._icons[name] = icon
        button = self._nav_button(self.items, f"{icon}   {name}", lambda: self.set(name, notify=True))
        button.grid(row=len(self._buttons), column=0, sticky="ew", pady=1)
        self._buttons[name] = button
        if self._current is None:
            self.set(name, notify=False)
        return frame

    def set(self, name: str, notify: bool = False) -> None:
        if name == self._current:
            if notify and self._command:
                self._command()
            return
        if self._current:
            self._frames[self._current].grid_remove()
            self._style(self._buttons[self._current], active=False)
        self._current = name
        self._frames[name].grid()
        self._style(self._buttons[name], active=True)
        if notify and self._command:
            self._command()

    def get(self) -> str:
        return self._current or ""

    def add_tool(self, text: str, command: Callable[[], None]) -> ctk.CTkButton:
        button = self._nav_button(self.footer, text, command)
        button.grid(row=self._footer_rows, column=0, sticky="ew", pady=1)
        self._footer_rows += 1
        return button

    # -- styling ------------------------------------------------------------------------------------------

    @staticmethod
    def _nav_button(master: tk.Misc, text: str, command: Callable[[], None]) -> ctk.CTkButton:
        return ctk.CTkButton(master, text=text, anchor="w", height=36, corner_radius=10, command=command,
                             font=theme.font(13), **theme.GHOST)

    @staticmethod
    def _style(button: ctk.CTkButton, active: bool) -> None:
        if active:
            button.configure(fg_color=theme.ACCENT_SOFT, hover_color=theme.ACCENT_SOFT, text_color=theme.ACCENT,
                             font=theme.font(13, "bold"))
        else:
            button.configure(font=theme.font(13), **theme.GHOST)
