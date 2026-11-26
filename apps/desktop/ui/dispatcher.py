"""Thread-safe bridge from worker threads to the Tk main loop.

Tkinter is not thread-safe, so workers never touch widgets (or even call `after`).
They `post()` a callable into a queue that the main thread drains on a timer.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from typing import Any, Protocol

logger = logging.getLogger(__name__)

_POLL_MS = 30


class _Scheduler(Protocol):
    def after(self, ms: int, func: Callable[[], Any]) -> Any: ...


class UiDispatcher:
    """Runs callables on the main thread. Create it on the main thread and call `start()` once."""

    def __init__(self, root: _Scheduler):
        self._root = root
        self._queue: queue.Queue[Callable[[], Any]] = queue.Queue()
        self._closed = False

    def start(self) -> None:
        self._drain()

    def close(self) -> None:
        self._closed = True

    def post(self, func: Callable[..., Any], *args: Any) -> None:
        """Schedule `func(*args)` on the main thread. Safe to call from any thread."""
        self._queue.put(lambda: func(*args))

    def run_in_thread(
        self,
        work: Callable[[], Any],
        on_success: Callable[[Any], Any] | None = None,
        on_error: Callable[[Exception], Any] | None = None,
    ) -> None:
        """Run `work` on a daemon thread, then deliver the result/exception on the main thread."""

        def runner() -> None:
            try:
                result = work()
            except Exception as exc:  # delivered to the UI, never swallowed
                if on_error:
                    self.post(on_error, exc)
                else:
                    logger.exception("Background task failed")
                return
            if on_success:
                self.post(on_success, result)

        threading.Thread(target=runner, daemon=True).start()

    def _drain(self) -> None:
        if self._closed:
            return
        while True:
            try:
                task = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                task()
            except Exception:
                logger.exception("UI callback failed")
        self._root.after(_POLL_MS, self._drain)
