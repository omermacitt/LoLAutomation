"""RunePilot skin query service — LCU skin data lookups."""

from __future__ import annotations

from rune_pilot.infrastructure.lcu_client import lcu_request


def get_skin_options_for_champion(champ_id: int) -> tuple[dict[int, str], set[int]]:
    """
    Returns skin names and owned skin IDs for a champion.

    Returns: (skin_name_by_id, owned_skin_ids)
    """
    champ_id_int = int(champ_id)
    base_skin_id = champ_id_int * 1000

    skin_name_by_id: dict[int, str] = {}
    try:
        champ_res = lcu_request("GET", f"/lol-game-data/assets/v1/champions/{champ_id_int}.json")
        if champ_res.status_code == 200:
            champ_json = champ_res.json()
            skins = champ_json.get("skins") if isinstance(champ_json, dict) else None
            if isinstance(skins, list):
                for s in skins:
                    if not isinstance(s, dict):
                        continue
                    try:
                        sid = int(s.get("id"))
                    except (TypeError, ValueError):
                        continue
                    name = s.get("name")
                    if isinstance(name, str) and name.strip():
                        skin_name_by_id[sid] = name.strip()
    except Exception:
        pass

    owned_skin_ids: set[int] = set()
    try:
        inv_res = lcu_request("GET", "/lol-inventory/v2/inventory/CHAMPION_SKIN")
        if inv_res.status_code == 200:
            inv = inv_res.json()
            if isinstance(inv, list):
                lo = base_skin_id
                hi = base_skin_id + 1000
                for item in inv:
                    if not isinstance(item, dict):
                        continue
                    if item.get("owned") is not True:
                        continue
                    try:
                        sid = int(item.get("itemId"))
                    except (TypeError, ValueError):
                        continue
                    if lo <= sid < hi and sid != base_skin_id:
                        owned_skin_ids.add(sid)
    except Exception:
        pass

    return skin_name_by_id, owned_skin_ids
