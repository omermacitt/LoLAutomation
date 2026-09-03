"""RunePilot champion query service — LCU champion list and info lookups."""

from __future__ import annotations

from typing import Any

from rune_pilot.infrastructure.lcu_client import lcu_request
from rune_pilot.domain.champion_service import normalize_champion_id, champion_slug_from_alias

# In-process caches populated from LCU data.
CHAMP_SLUG_BY_ID: dict[int, str] = {}
CHAMP_NAME_BY_ID: dict[int, str] = {}


def get_champion_slug_by_id(champ_id: int) -> str | None:
    """Resolves the runes.json slug for a champion ID from LCU data (cached)."""
    if champ_id in CHAMP_SLUG_BY_ID:
        return CHAMP_SLUG_BY_ID[champ_id]

    try:
        res = lcu_request("GET", "/lol-game-data/assets/v1/champion-summary.json")
        if res.status_code != 200:
            return None
        champs = res.json()
        if not isinstance(champs, list):
            return None

        for champ in champs:
            if not isinstance(champ, dict):
                continue
            cid = champ.get("id")
            try:
                cid_int = int(cid)
            except (TypeError, ValueError):
                continue

            name = champ.get("name") or champ.get("alias") or ""
            if name and cid_int not in CHAMP_NAME_BY_ID:
                CHAMP_NAME_BY_ID[cid_int] = str(name)

            alias = champ.get("alias") or champ.get("name") or ""
            slug = champion_slug_from_alias(str(alias))
            if slug:
                CHAMP_SLUG_BY_ID[cid_int] = slug

        return CHAMP_SLUG_BY_ID.get(champ_id)
    except Exception:
        return None


def get_champion_name_by_id(champ_id: int) -> str | None:
    """Returns the display name for a champion ID from LCU data (cached)."""
    if champ_id in CHAMP_NAME_BY_ID:
        return CHAMP_NAME_BY_ID[champ_id]
    get_champion_slug_by_id(champ_id)
    return CHAMP_NAME_BY_ID.get(champ_id)


def get_champion_summary() -> list[dict[str, Any]]:
    """Returns all champions from the LCU (used for ban dropdowns)."""
    try:
        res = lcu_request("GET", "/lol-game-data/assets/v1/champion-summary.json")
        if res.status_code != 200:
            return []
        data = res.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []


def get_owned_champions_raw() -> list[dict[str, Any]]:
    """Returns the raw list of owned champions from the LCU."""
    try:
        res = lcu_request("GET", "/lol-champions/v1/owned-champions-minimal")
        if res.status_code != 200:
            return []
        data = res.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []


def load_champions_map() -> dict[int, dict[str, Any]]:
    """
    Reads the player's owned champions from the LCU.

    Return format: `{championId: {"id": int, "name": str, "alias": str}}`
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
    """Returns the owned champion list for the UI."""
    champs_map = load_champions_map()
    if not champs_map:
        return []
    return sorted(champs_map.values(), key=lambda x: x.get("name", ""))
