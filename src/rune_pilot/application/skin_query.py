"""Skin catalog queries against the injected League Client."""

from rune_pilot.application.ports.league_client import LeagueClient


class SkinQuery:
    def __init__(self, client: LeagueClient):
        self._client = client

    def get_skin_options_for_champion(self, champ_id: int, *, strict: bool = False) -> tuple[dict[int, str], set[int]]:
        """
        Returns skin names and owned skin IDs for a champion.

        Returns: (skin_name_by_id, owned_skin_ids)
        """
        champ_id_int = int(champ_id)
        base_skin_id = champ_id_int * 1000

        skin_name_by_id: dict[int, str] = {}
        try:
            champ_res = self._client.champion_data(champ_id_int)
            if strict:
                champ_res.raise_for_status()
            if champ_res.status_code == 200:
                champ_json = champ_res.json()
                skins = champ_json.get("skins") if isinstance(champ_json, dict) else None
                if strict and not isinstance(skins, list):
                    raise ValueError("Unexpected champion skin data")
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
            if strict:
                raise
            pass

        owned_skin_ids: set[int] = set()
        try:
            inv_res = self._client.skin_inventory()
            if strict:
                inv_res.raise_for_status()
            if inv_res.status_code == 200:
                inv = inv_res.json()
                if strict and not isinstance(inv, list):
                    raise ValueError("Unexpected skin ownership data")
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
            if strict:
                raise
            pass

        return skin_name_by_id, owned_skin_ids
