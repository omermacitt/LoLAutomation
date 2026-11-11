"""Thread-safe, transient selection feedback, separate from persisted settings."""

import threading

from rune_pilot.domain.selection_notice import SelectionNotice


class SelectionFeedback:
    def __init__(self):
        self._lock = threading.Lock()
        self._counter = 0
        self._notice: SelectionNotice | None = None
        self._context = None
        self._rune_notice: SelectionNotice | None = None
        self._rune_context = None

    def publish_rune(self, context: tuple, code: str, role: str, champion_id: int):
        with self._lock:
            if self._rune_context == context and self._rune_notice is not None:
                return
            self._counter += 1
            self._rune_context = context
            self._rune_notice = SelectionNotice(
                id=self._counter, code=code, role=role, champion_id=champion_id
            )

    def clear_rune(self):
        with self._lock:
            self._rune_notice = None
            self._rune_context = None

    def read_rune(self) -> SelectionNotice | None:
        with self._lock:
            return self._rune_notice.model_copy(deep=True) if self._rune_notice else None

    def publish(self, context: tuple, code: str, role: str, champion_id: int | None = None):
        with self._lock:
            if self._context == context and self._notice is not None:
                return
            self._counter += 1
            self._context = context
            self._notice = SelectionNotice(
                id=self._counter, code=code, role=role, champion_id=champion_id
            )

    def clear(self):
        with self._lock:
            self._notice = None
            self._context = None

    def read(self) -> SelectionNotice | None:
        with self._lock:
            return self._notice.model_copy(deep=True) if self._notice else None
