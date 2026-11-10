"""Champion queries against the injected League Client, with per-instance metadata caches."""

import threading
from typing import Any

from rune_pilot.application.ports.league_client import ClientReply, LeagueClient
from rune_pilot.domain.champion_service import (
    champion_slug_from_alias,
    is_mode_champion_variant,
    normalize_champion_id,
)


class ChampionQuery:
    def __init__(self, client: LeagueClient):
        self._client = client
        self._lock = threading.RLock()
        self._slug_by_id: dict[int, str] = {}
        self._name_by_id: dict[int, str] = {}

    def get_champion_slug_by_id(self, champ_id: int) -> str | None:
        with self._lock:
            if champ_id in self._slug_by_id:
                return self._slug_by_id[champ_id]
            try:
                response = self._client.champion_summary()
                if response.status_code != 200:
                    return None
                champions = response.json()
                if not isinstance(champions, list):
                    return None
                for champion in champions:
                    if not isinstance(champion, dict) or is_mode_champion_variant(champion):
                        continue
                    try:
                        cid = int(champion.get("id"))
                    except (TypeError, ValueError):
                        continue
                    name = champion.get("name") or champion.get("alias") or ""
                    if name:
                        self._name_by_id.setdefault(cid, str(name))
                    alias = champion.get("alias") or champion.get("name") or ""
                    slug = champion_slug_from_alias(str(alias))
                    if slug:
                        self._slug_by_id[cid] = slug
                return self._slug_by_id.get(champ_id)
            except Exception:
                return None

    def get_champion_name_by_id(self, champ_id: int) -> str | None:
        with self._lock:
            if champ_id not in self._name_by_id:
                self.get_champion_slug_by_id(champ_id)
            return self._name_by_id.get(champ_id)

    @staticmethod
    def _read_list(read, *, strict: bool) -> list[dict[str, Any]]:
        try:
            response: ClientReply = read()
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError("Unexpected champion data")
            return data
        except Exception:
            if strict:
                raise
            return []

    def get_champion_summary(self, *, strict: bool = False) -> list[dict[str, Any]]:
        return self._read_list(self._client.champion_summary, strict=strict)

    def get_owned_champions_raw(self, *, strict: bool = False) -> list[dict[str, Any]]:
        return self._read_list(self._client.owned_champions, strict=strict)

    def load_champions_map(self) -> dict[int, dict[str, Any]]:
        try:
            response = self._client.owned_champions()
            if response.status_code != 200:
                return {}
            champions = response.json()
            if not isinstance(champions, list):
                return {}
            result: dict[int, dict[str, Any]] = {}
            for champion in champions:
                if not isinstance(champion, dict) or is_mode_champion_variant(champion):
                    continue
                cid = normalize_champion_id(champion.get("id"))
                if cid is None:
                    continue
                ownership = champion.get("ownership") or {}
                if isinstance(ownership, dict) and ownership.get("owned") is False:
                    continue
                result[cid] = {
                    "id": cid,
                    "name": str(champion.get("name") or "Unknown"),
                    "alias": str(champion.get("alias") or ""),
                }
            return result
        except Exception as e:
            print(f"[API] Error loading owned champions: {e}")
            return {}

    def get_champions(self) -> list[dict[str, Any]]:
        return sorted(self.load_champions_map().values(), key=lambda item: item["name"])
