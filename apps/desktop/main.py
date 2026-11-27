"""Entry point: `python main.py` from apps/desktop (backend must be running)."""

from __future__ import annotations

import logging
from typing import Any

import auth_store
from api_client import ApiClient, ApiError
from player.audio_output import PygameOutput
from ui.app import App
from ui.login import LoginWindow


def restore_session(api: ApiClient) -> dict[str, Any] | None:
    """The saved sign-in if the backend still accepts it. A refusal deletes it; no connection keeps it."""
    saved = auth_store.load()
    if not saved:
        return None
    api.set_token(saved["token"])
    try:
        user = api.me()
    except ApiError as exc:
        if exc.is_connection_error:
            return saved  # the backend is down, not the account: let the app show its own error banner
        api.set_token(None)
        auth_store.clear()
        return None
    return {"token": saved["token"], "user": user}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    api, output = ApiClient(), PygameOutput()
    session = restore_session(api)
    notice: str | None = None
    while True:
        if session is None:
            session = LoginWindow(api, notice).run()
            if session is None:
                break  # the sign-in window was closed
            api.set_token(session["token"])
            auth_store.save(session["token"], session["user"])
        app = App(api, output, session["user"])
        app.mainloop()
        api.on_unauthorized = None
        if not app.logout_requested:
            break
        notice = "Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại." if app.session_expired else None
        api.set_token(None)
        auth_store.clear()
        session = None


if __name__ == "__main__":
    main()
