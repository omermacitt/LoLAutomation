"""One in-flight read, performed off the UI thread, with close-safe results."""

import threading
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal


class BackgroundQuery(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()
    _result = pyqtSignal(object, str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.busy = False
        self._closed = threading.Event()
        self._result.connect(self._deliver)

    def run(self, query: Callable[[], Any]) -> bool:
        if self.busy or self._closed.is_set():
            return False
        self.busy = True

        def worker():
            try:
                result, error = query(), ""
            except Exception as e:
                result, error = None, str(e) or type(e).__name__
            if not self._closed.is_set():
                self._result.emit(result, error)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def _deliver(self, result: Any, error: str):
        if self._closed.is_set():
            self.busy = False
            return
        if error:
            self.failed.emit(error)
        else:
            self.succeeded.emit(result)
        self.busy = False
        self.finished.emit()

    def shutdown(self):
        self._closed.set()
