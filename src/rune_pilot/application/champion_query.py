"""
RunePilot şampiyon sorgu servisi.

LCU üzerinden şampiyon listesi ve bilgisi sorgulama.
"""

from __future__ import annotations

from typing import Any

from src.rune_pilot.infrastructure.lcu_client import lcu_request
from src.rune_pilot.domain.champion_service import normalize_champion_id


def load_champions_map() -> dict[int, dict[str, Any]]:
    """
    LCU üzerinden oyuncunun sahip olduğu şampiyonları okur.

    Dönüş formatı: `{championId: {"id": int, "name": str, "alias": str}}`
    """
    try:
        res = lcu_request("GET", "/lol-champions/v1/owned-champions-minimal")
        if res.status_code != 200:
            return {}

        champs = res.json()
        if not isinstance(champs, list):
            return {}

        valid_champs: dict[int, dict[str, Any]] = {}
        for champ in champs:
            if not isinstance(champ, dict):
                continue

            cid = normalize_champion_id(champ.get("id"))
            if cid is None:
                continue

            ownership = champ.get("ownership") or {}
            if isinstance(ownership, dict) and ownership.get("owned") is False:
                continue

            valid_champs[cid] = {
                "id": cid,
                "name": str(champ.get("name") or "Unknown"),
                "alias": str(champ.get("alias") or ""),
            }

        return valid_champs
    except Exception as e:
        print(f"[API] Error loading owned champions: {e}")
        return {}


def get_champions() -> list[dict[str, Any]]:
    """UI için sahip olunan şampiyon listesini döndürür."""
    champs_map = load_champions_map()
    if not champs_map:
        return []
    return sorted(champs_map.values(), key=lambda x: x.get("name", ""))
