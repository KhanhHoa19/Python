"""Entry point: `python main.py` from apps/desktop (backend must be running)."""

from __future__ import annotations

import logging

from api_client import ApiClient
from player.audio_output import PygameOutput
from ui.app import App


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    App(ApiClient(), PygameOutput()).mainloop()


if __name__ == "__main__":
    main()
