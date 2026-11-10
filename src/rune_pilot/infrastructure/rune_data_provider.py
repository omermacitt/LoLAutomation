"""Lazy, instance-owned recommendation data loaded from the bundled JSON file."""

import json
import os
import threading
from copy import deepcopy
from typing import Any

from rune_pilot.shared.resource import resource_path


class JsonRuneData:
    def __init__(self, path: str | None = None):
        self.path = path if path is not None else resource_path("runes.json")
        self._data: dict[str, Any] | None = None
        self._lock = threading.Lock()

    def get_runes_data(self) -> dict[str, Any]:
        with self._lock:
            if self._data is None:
                self._data = self._load()
            return deepcopy(self._data)

    def _load(self) -> dict[str, Any]:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, encoding="utf-8") as source:
                data = json.load(source)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}
