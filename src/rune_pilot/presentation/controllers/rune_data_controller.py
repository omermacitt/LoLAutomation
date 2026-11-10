"""Share one rune catalog and a deduplicated icon queue across preset editors."""

from collections import deque

from PyQt6.QtCore import QObject, pyqtSignal

from rune_pilot.domain.game_data import RuneCatalog
from rune_pilot.presentation.api_client import ApiClient
from rune_pilot.presentation.controllers.background_query import BackgroundQuery


class RuneDataController(QObject):
    loaded = pyqtSignal(object)
    failed = pyqtSignal(str)
    icon_loaded = pyqtSignal(int, object)

    def __init__(self, client: ApiClient | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._client = client if client is not None else ApiClient()
        self.catalog: RuneCatalog | None = None
        self._catalog_query = BackgroundQuery(self)
        self._catalog_query.succeeded.connect(self._on_catalog)
        self._catalog_query.failed.connect(self.failed)
        self._icon_query = BackgroundQuery(self)
        self._icon_query.succeeded.connect(self._on_icon)
        self._icon_query.failed.connect(lambda _error: self._on_icon(None))
        self._icon_query.finished.connect(self._next_icon)
        self._icons: dict[int, bytes | None] = {}
        self._queued: set[int] = set()
        self._queue: deque[int] = deque()
        self._current_icon: int | None = None
        self._closed = False

    def load(self):
        if not self._closed and self.catalog is None:
            self._catalog_query.run(self._client.rune_catalog)

    def _on_catalog(self, catalog: RuneCatalog):
        self.catalog = catalog
        self.loaded.emit(catalog)

    def icon(self, perk_id: int) -> bytes | None:
        if perk_id in self._icons:
            return self._icons[perk_id]
        if not self._closed and perk_id not in self._queued:
            self._queued.add(perk_id)
            self._queue.append(perk_id)
            self._next_icon()
        return None

    def _next_icon(self):
        if self._closed or self._icon_query.busy or not self._queue:
            return
        perk_id = self._queue.popleft()
        self._current_icon = perk_id
        self._icon_query.run(lambda: self._client.perk_icon(perk_id))

    def _on_icon(self, data: bytes | None):
        if self._current_icon is not None:
            perk_id = self._current_icon
            self._icons[perk_id] = data
            self._current_icon = None
            self.icon_loaded.emit(perk_id, data)

    def shutdown(self):
        self._closed = True
        self._catalog_query.shutdown()
        self._icon_query.shutdown()
        self._queue.clear()
