"""
RunePilot rün verisi sağlayıcısı.

`runes.json` dosyasını okur ve rün verisine erişim sağlar.
"""

from __future__ import annotations

import json
import os
from typing import Any

from src.rune_pilot.shared.resource import resource_path

RUNES_FILE = resource_path("runes.json")

_RUNES_DATA: dict[str, Any] | None = None


def load_runes() -> dict[str, Any]:
    """`runes.json` içeriğini okur; hata durumunda boş dict döndürür."""
    if not os.path.exists(RUNES_FILE):
        return {}
    try:
        with open(RUNES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_runes_data() -> dict[str, Any]:
    """Rün verisini döndürür (ilk çağrıda yüklenir)."""
    global _RUNES_DATA
    if _RUNES_DATA is None:
        _RUNES_DATA = load_runes()
    return _RUNES_DATA
