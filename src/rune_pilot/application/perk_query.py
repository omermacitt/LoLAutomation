"""
RunePilot perk (rün) sorgu servisi.

LCU üzerinden rün style/perk verisi ve ikon sorgulama.
"""

from __future__ import annotations

from typing import Any

from src.rune_pilot.infrastructure.lcu_client import lcu_request

_PERK_STYLES_CACHE: list[dict[str, Any]] | None = None
_PERKS_CACHE: list[dict[str, Any]] | None = None


def get_perk_styles() -> list[dict[str, Any]]:
    """LCU üzerinden rune style listesini okur (process başına cache'li)."""
    global _PERK_STYLES_CACHE
    if _PERK_STYLES_CACHE is not None:
        return _PERK_STYLES_CACHE
    res = lcu_request("GET", "/lol-perks/v1/styles")
    res.raise_for_status()
    data = res.json()
    if not isinstance(data, list):
        raise ValueError("Unexpected response from /lol-perks/v1/styles")
    _PERK_STYLES_CACHE = data
    return data


def get_perks() -> list[dict[str, Any]]:
    """LCU üzerinden perk listesini okur (farklı endpoint'lere fallback, cache'li)."""
    global _PERKS_CACHE
    if _PERKS_CACHE is not None:
        return _PERKS_CACHE
    endpoints = (
        "/lol-perks/v1/perks",
        "/lol-game-data/assets/v1/perks.json",
    )
    last_error: Exception | None = None
    for endpoint in endpoints:
        try:
            res = lcu_request("GET", endpoint)
            res.raise_for_status()
            data = res.json()
            if isinstance(data, list):
                _PERKS_CACHE = data
                return data
            if isinstance(data, dict) and isinstance(data.get("perks"), list):
                _PERKS_CACHE = data["perks"]
                return data["perks"]
            last_error = ValueError(f"Unexpected response from {endpoint}")
        except Exception as e:
            last_error = e
            continue
    raise ValueError("Could not fetch perks") from last_error


def get_perk_icon_bytes(asset_path: str) -> bytes | None:
    """Verilen LCU asset yolu için ikon baytlarını döndürür."""
    try:
        res = lcu_request("GET", asset_path)
        if res.status_code != 200:
            return None
        return res.content
    except Exception:
        return None
