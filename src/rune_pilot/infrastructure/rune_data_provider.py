"""RunePilot rune data provider — reads runes.json and exposes rune data."""

from __future__ import annotations

import json
import os
from typing import Any

from src.rune_pilot.shared.resource import resource_path

RUNES_FILE = resource_path("runes.json")

_RUNES_DATA: dict[str, Any] | None = None


def load_runes() -> dict[str, Any]:
    """Reads `runes.json`; returns an empty dict on error."""
    if not os.path.exists(RUNES_FILE):
        return {}
    try:
        with open(RUNES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_runes_data() -> dict[str, Any]:
    """Returns the rune data, loading it on first call."""
    global _RUNES_DATA
    if _RUNES_DATA is None:
        _RUNES_DATA = load_runes()
    return _RUNES_DATA
