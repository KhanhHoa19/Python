"""S09 – Đăng nhập & Đăng ký: the window shown before the app when nobody is signed in."""

from __future__ import annotations

from typing import Any

import customtkinter as ctk

from api_client import ApiClient
from ui import theme
from ui.common import error_text
from ui.dispatcher import UiDispatcher
from ui.viewmodels import check_credentials


class LoginWindow(ctk.CTk):
    """Run with `run()`: returns {"token", "user"} after a successful sign-in, or None if the window was closed."""

    def __init__(self, api: ApiClient, notice: str | None = None):
        super().__init__()
        self.api = api
        self.result: dict[str, Any] | None = None
        self.mode = "login"
        ctk.set_appearance_mode(theme.load_appearance())
        theme.apply()
        self.configure(fg_color=theme.BG)
        self.title("Audiobook TTS – Đăng nhập")
        self.geometry("460x760")
        self.minsize(420, 720)
        self.ui = UiDispatcher(self)
        self.protocol("WM_DELETE_WINDOW", self._close)

        card = ctk.CTkFrame(self, border_width=1, border_color=theme.BORDER, corner_radius=18, width=404)
        card.pack(side="left", fill="both", expand=True, padx=28, pady=28)
        card.columnconfigure(0, weight=1)
        brand = ctk.CTkFrame(card, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w", padx=28, pady=(26, 6))
        ctk.CTkLabel(brand, text="🎧", width=38, height=38, corner_radius=11, fg_color=theme.ACCENT,
                     text_color=theme.ACCENT_INK, font=theme.font(18)).pack(side="left")
        ctk.CTkLabel(brand, text="Audiobook ", font=theme.font(16, "bold")).pack(side="left", padx=(10, 0))
        ctk.CTkLabel(brand, text="TTS", font=theme.font(16, "bold"), text_color=theme.ACCENT).pack(side="left")

        self.heading = ctk.CTkLabel(card, text="", anchor="w", font=theme.font(24, "bold"))
        self.heading.grid(row=1, column=0, sticky="ew", padx=28, pady=(14, 0))
        self.subtitle = ctk.CTkLabel(card, text="", anchor="w", text_color=theme.MUTED, wraplength=340, justify="left")
        self.subtitle.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 12))
        self.tabs = ctk.CTkSegmentedButton(card, values=["Đăng nhập", "Đăng ký"], command=self._tab_chosen)
        self.tabs.set("Đăng nhập")
        self.tabs.grid(row=3, column=0, sticky="ew", padx=28, pady=(0, 8))

        self.notice = ctk.CTkLabel(card, text=notice or "", anchor="w", text_color=theme.WARNING, wraplength=340, justify="left")
        self.notice.grid(row=4, column=0, sticky="ew", padx=28)

        form = ctk.CTkFrame(card, fg_color="transparent")
        form.grid(row=5, column=0, sticky="ew", padx=28)
        form.columnconfigure(0, weight=1)
        self.rows: dict[str, tuple[ctk.CTkLabel, ctk.CTkEntry]] = {}
        for index, (key, label, secret) in enumerate((
            ("username", "Tên đăng nhập", False), ("full_name", "Tên hiển thị (không bắt buộc)", False),
            ("password", "Mật khẩu", True), ("confirm", "Nhập lại mật khẩu", True),
        )):
            caption = ctk.CTkLabel(form, text=label, anchor="w", text_color=theme.TEXT_2, font=theme.font(12))
            entry = ctk.CTkEntry(form, show="•" if secret else "", height=36)
            caption.grid(row=index * 2, column=0, sticky="ew", pady=(10, 2))
            entry.grid(row=index * 2 + 1, column=0, sticky="ew")
            entry.bind("<Return>", lambda _e: self._submit())
            self.rows[key] = (caption, entry)

        self.status = ctk.CTkLabel(card, text="", anchor="w", text_color=theme.DANGER, wraplength=340, justify="left")
        self.status.grid(row=6, column=0, sticky="ew", padx=28, pady=(10, 0))
        self.submit_btn = ctk.CTkButton(card, text="Đăng nhập", height=40, command=self._submit)
        self.submit_btn.grid(row=7, column=0, sticky="ew", padx=28, pady=(8, 26))
        self._apply_mode()
        self.after(200, lambda: self.rows["username"][1].focus_set())
        self.demo_panel: ctk.CTkFrame | None = None
        self.ui.run_in_thread(self.api.demo_accounts, self._show_demo_accounts, lambda _exc: None)

    # -- development: one-click accounts ------------------------------------------------------------------

    def _show_demo_accounts(self, accounts: list[dict[str, Any]]) -> None:
        """Boxes in a second column, only when the backend runs with DEV_QUICK_LOGIN=true."""
        from ui.viewmodels import avatar_letter

        if not accounts or self.demo_panel is not None:
            return
        self.minsize(860, 720)
        self.geometry("900x760")
        panel = ctk.CTkFrame(self, fg_color="transparent", width=312)
        panel.pack(side="right", fill="y", padx=(0, 28), pady=28)
        self.demo_panel = panel
        ctk.CTkLabel(panel, text="TÀI KHOẢN THỬ", anchor="w", text_color=theme.TEXT_2, font=theme.font(11, "bold")).pack(fill="x")
        ctk.CTkLabel(panel, text="Chế độ phát triển · bấm để đăng nhập", anchor="w", text_color=theme.MUTED,
                     font=theme.font(11)).pack(fill="x", pady=(0, 10))
        for account in accounts:
            box = ctk.CTkFrame(panel, border_width=1, border_color=theme.BORDER_STRONG, corner_radius=14, width=300, height=96)
            box.pack(fill="x", pady=6)
            box.pack_propagate(False)
            ctk.CTkLabel(box, text=avatar_letter(account), width=40, height=40, corner_radius=20, fg_color=theme.ACCENT_SOFT,
                         text_color=theme.ACCENT, font=theme.font(15, "bold")).pack(side="left", padx=(14, 10))
            text = ctk.CTkFrame(box, fg_color="transparent")
            text.pack(side="left", fill="x", expand=True)
            is_admin = account["role"] == "admin"
            labels = [
                ctk.CTkLabel(text, text=f"{account['full_name']}   {'ADMIN' if is_admin else 'MEMBER'}", anchor="w",
                             font=theme.font(13, "bold")),
                ctk.CTkLabel(text, text=account["username"], anchor="w", text_color=theme.TEXT_2, font=theme.font(12)),
                ctk.CTkLabel(text, text=account["password"], anchor="w", text_color=theme.MUTED, font=theme.font(12)),
            ]
            for label in labels:
                label.pack(fill="x")
            for widget in (box, text, *labels):  # the whole box is the button
                widget.bind("<Button-1>", lambda _e, a=account: self._quick_login(a))
                widget.configure(cursor="hand2")

    def _quick_login(self, account: dict[str, Any]) -> None:
        self.status.configure(text="")
        self.submit_btn.configure(state="disabled", text="Đang xử lý…")
        self.ui.run_in_thread(lambda: self.api.login(account["username"], account["password"]), self._signed_in, self._failed)

    # -- behaviour ---------------------------------------------------------------------------------------

    def _tab_chosen(self, label: str) -> None:
        self.mode = "register" if label == "Đăng ký" else "login"
        self.status.configure(text="")
        self._apply_mode()

    def _apply_mode(self) -> None:
        register = self.mode == "register"
        self.heading.configure(text="Tạo tài khoản" if register else "Chào mừng trở lại")
        self.subtitle.configure(text="Mỗi người có thư viện, tiến độ và giọng đọc riêng." if register
                                else "Đăng nhập để nghe tiếp từ chỗ bạn dừng.")
        self.submit_btn.configure(text="Tạo tài khoản" if register else "Đăng nhập")
        for key in ("full_name", "confirm"):
            for widget in self.rows[key]:
                widget.grid() if register else widget.grid_remove()

    def _submit(self) -> None:
        username = self.rows["username"][1].get()
        password = self.rows["password"][1].get()
        problem = check_credentials(self.mode, username, password, self.rows["confirm"][1].get())
        if problem:
            self.status.configure(text=problem)
            return
        self.status.configure(text="")
        self.notice.configure(text="")
        self.submit_btn.configure(state="disabled", text="Đang xử lý…")
        full_name = self.rows["full_name"][1].get().strip()
        mode = self.mode

        def work() -> dict[str, Any]:
            if mode == "login":
                return self.api.login(username.strip(), password)
            return self.api.register(username.strip(), password, full_name)

        self.ui.run_in_thread(work, self._signed_in, self._failed)

    def _signed_in(self, response: dict[str, Any]) -> None:
        self.result = {"token": response["access_token"], "user": response["user"]}
        self._close()

    def _failed(self, exc: Exception) -> None:
        self.status.configure(text=error_text(exc))
        self.submit_btn.configure(state="normal", text="Tạo tài khoản" if self.mode == "register" else "Đăng nhập")

    def _close(self) -> None:
        self.ui.close()
        self.destroy()

    def run(self) -> dict[str, Any] | None:
        self.ui.start()
        self.mainloop()
        return self.result
