"""Background update HTTP requests and close-safe delivery to the desktop."""

import os
import webbrowser

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from rune_pilot.domain.update import UpdateDownload, UpdateInfo
from rune_pilot.presentation.api_client import ApiClient
from rune_pilot.presentation.controllers.background_query import BackgroundQuery

CHECK_DELAY_MS = 1500


class UpdateController(QObject):
    update_available = pyqtSignal(object)
    download_started = pyqtSignal()
    download_finished = pyqtSignal(bool, str, str)

    def __init__(self, parent: QObject | None = None, *, api_client: ApiClient | None = None):
        super().__init__(parent)
        self._client = api_client if api_client is not None else ApiClient()
        self._closed = False
        self._check_started = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._check_async)
        self._check = BackgroundQuery(self)
        self._check.succeeded.connect(self._on_check)
        self._download = BackgroundQuery(self)
        self._download.succeeded.connect(self._on_download)
        self._download.failed.connect(lambda error: self.download_finished.emit(False, "", error))

    def schedule_check(self) -> None:
        if self._closed or self._check_started:
            return
        self._check_started = True
        self._timer.start(CHECK_DELAY_MS)

    def _check_async(self) -> None:
        self._check.run(self._client.check_update)

    def _on_check(self, info: UpdateInfo | None) -> None:
        # Check failures and unavailable releases remain silent.
        if info is not None:
            self.update_available.emit(info)

    def download(self, info: UpdateInfo) -> None:
        if self._closed or self._download.busy:
            return
        if not info.asset_download_url:
            self.open_release_page(info)
            return
        if self._download.run(lambda: self._client.download_update(info.update_id)):
            self.download_started.emit()

    def _on_download(self, result: UpdateDownload) -> None:
        self.download_finished.emit(True, result.installer_path, "")

    def shutdown(self) -> None:
        self._closed = True
        self._timer.stop()
        self._check.shutdown()
        self._download.shutdown()

    @staticmethod
    def launch_installer(path: str) -> None:
        os.startfile(path)  # type: ignore[attr-defined]

    @staticmethod
    def open_release_page(info: UpdateInfo) -> None:
        url = info.release_html_url.strip()
        if url:
            try:
                webbrowser.open(url)
            except Exception:
                pass
