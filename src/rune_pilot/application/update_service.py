"""Offer discovered releases and download only registered installer assets."""

import threading
from collections import OrderedDict
from uuid import uuid4

from rune_pilot.application.ports.update_source import UpdateSource
from rune_pilot.domain.update import UpdateDownload, UpdateInfo, select_update


class UnknownUpdate(LookupError):
    pass


class UpdateDownloadFailed(RuntimeError):
    pass


class UpdateService:
    def __init__(self, source: UpdateSource, *, current_version: str, enabled: bool = True):
        self._source = source
        self._version = current_version
        self._enabled = enabled
        self._lock = threading.Lock()
        self._downloads_lock = threading.Lock()
        self._offers: OrderedDict[str, UpdateInfo] = OrderedDict()
        self._downloaded: dict[str, UpdateDownload] = {}

    def check(self) -> UpdateInfo | None:
        if not self._enabled:
            return None
        try:
            data = self._source.latest_release()
            info = select_update(data, self._version) if isinstance(data, dict) else None
        except Exception:
            return None  # Offline and rate-limited checks remain silent.
        if info is None:
            return None
        with self._lock:
            for existing in self._offers.values():
                if existing.model_dump(exclude={"update_id"}) == info.model_dump(
                    exclude={"update_id"}
                ):
                    return existing.model_copy(deep=True)
            info.update_id = str(uuid4())
            self._offers[info.update_id] = info
            while len(self._offers) > 8:
                key, _ = self._offers.popitem(last=False)
                self._downloaded.pop(key, None)
            return info.model_copy(deep=True)

    def download(self, update_id: str) -> UpdateDownload:
        # Serial downloads avoid duplicate writes after retries or double clicks.
        with self._downloads_lock:
            with self._lock:
                info = self._offers.get(update_id)
                if info is None or not info.asset_download_url:
                    raise UnknownUpdate("Update installer unavailable; check for updates again")
                cached = self._downloaded.get(update_id)
                if cached is not None:
                    return cached.model_copy()
                info = info.model_copy(deep=True)
            try:
                path = self._source.download(info)
                if not path:
                    raise ValueError("Missing installer path")
            except Exception as error:
                # Avoid exposing auth headers, remote responses or local internals.
                raise UpdateDownloadFailed("Could not download the update installer") from error
            result = UpdateDownload(installer_path=path)
            with self._lock:
                if update_id in self._offers:
                    self._downloaded[update_id] = result
            return result.model_copy()
