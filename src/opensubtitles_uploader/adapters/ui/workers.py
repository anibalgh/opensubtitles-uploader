"""Generic background workers so the UI never blocks while hashing,
probing, or talking to OpenSubtitles."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal


class TaskWorker(QThread):
    """Run ``func(*args, **kwargs)`` in a thread; emit a result or error.

    Signals are emitted on the worker thread and delivered to slots in
    the GUI thread via Qt's queued connections.
    """

    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs
        self._result: Any = None

    def run(self) -> None:
        try:
            self._result = self._func(*self._args, **self._kwargs)
        except Exception as exc:
            self.failed.emit(exc)
            return
        self.succeeded.emit(self._result)

    def result(self) -> Any:
        return self._result
