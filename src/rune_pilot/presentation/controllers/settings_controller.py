"""Load settings before allowing edits; serialize and coalesce background saves."""

from __future__ import annotations

import threading

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from rune_pilot.domain.user_config import UserConfig
from rune_pilot.presentation.api_client import ApiClient

RETRY_MS = 1500
SAVE_DEBOUNCE_MS = 300


class SettingsController(QObject):
    loaded = pyqtSignal(object)
    ready_changed = pyqtSignal(bool)
    failed = pyqtSignal(str)
    saved = pyqtSignal()  # All queued saves have completed successfully.
    _load_finished = pyqtSignal(object, str)
    _save_finished = pyqtSignal(object, str)

    def __init__(self, client: ApiClient | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._client = client if client is not None else ApiClient()
        self._ready = False
        self._loading = False
        self._saving = False
        self._pending: UserConfig | None = None
        self._flushing = False
        self._closed = threading.Event()
        self._load_retry = QTimer(self)
        self._load_retry.setSingleShot(True)
        self._load_retry.timeout.connect(self.load)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._start_save)
        self._load_finished.connect(self._on_load_finished)
        self._save_finished.connect(self._on_save_finished)

    @property
    def ready(self) -> bool:
        return self._ready

    def load(self) -> None:
        """Retry startup reads until successful; never reload over local edits."""
        if self._closed.is_set() or self._ready or self._loading:
            return
        self._load_retry.stop()
        self._loading = True

        def worker() -> None:
            try:
                config = self._client.load_settings()
            except Exception as e:
                if not self._closed.is_set():
                    self._load_finished.emit(None, str(e) or type(e).__name__)
            else:
                if not self._closed.is_set():
                    self._load_finished.emit(config, "")

        threading.Thread(target=worker, daemon=True).start()

    def _on_load_finished(self, config: UserConfig | None, error: str) -> None:
        if self._closed.is_set():
            return
        self._loading = False
        if config is None:
            self.failed.emit(error)
            self._load_retry.start(RETRY_MS)
            return
        self._ready = True
        self.loaded.emit(config)
        self.ready_changed.emit(True)

    def save(self, config: UserConfig) -> bool:
        """Snapshot on the UI thread. No write is allowed before a successful load."""
        if self._closed.is_set() or not self._ready:
            return False
        self._pending = config.model_copy(deep=True)
        self._save_timer.start(SAVE_DEBOUNCE_MS)
        return True

    def flush(self) -> None:
        """Drain queued writes asynchronously, for window close or explicit save."""
        if self._closed.is_set():
            return
        self._flushing = True
        self._save_timer.stop()
        self._start_save()

    def shutdown(self) -> None:
        """Stop retries after close. Call only after flush, or before initial load."""
        self._closed.set()
        self._load_retry.stop()
        self._save_timer.stop()

    def _start_save(self) -> None:
        if self._closed.is_set() or self._saving:
            return
        if self._pending is None:
            if self._flushing:
                self._flushing = False
                self.saved.emit()
            return
        config = self._pending
        self._pending = None
        self._saving = True

        def worker() -> None:
            try:
                self._client.save_settings(config)
            except Exception as e:
                if not self._closed.is_set():
                    self._save_finished.emit(config, str(e) or type(e).__name__)
            else:
                if not self._closed.is_set():
                    self._save_finished.emit(config, "")

        threading.Thread(target=worker, daemon=True).start()

    def _on_save_finished(self, config: UserConfig, error: str) -> None:
        if self._closed.is_set():
            return
        self._saving = False
        if error:
            # A later edit is more recent than the failed write and must win.
            if self._pending is None:
                self._pending = config
            self._flushing = False
            self.failed.emit(error)
            self._save_timer.start(RETRY_MS)
        elif self._pending is not None:
            if self._flushing:
                self._start_save()
            else:
                self._save_timer.start(SAVE_DEBOUNCE_MS)
        else:
            self._flushing = False
            self.saved.emit()
