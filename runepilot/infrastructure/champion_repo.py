"""
Şampiyon verisi deposu (infrastructure).

LCU'dan şampiyon özet/sahiplik verisini okur ve id -> slug / id -> görünen ad
eşlemelerini cache'ler. Önceki `api.py`'deki modül-seviyesi global sözlükler
(`CHAMP_SLUG_BY_ID`, `CHAMP_NAME_BY_ID`) burada instance state olarak tutulur.
"""

from __future__ import annotations

from typing import Any

from runepilot.domain.champions import champion_slug_from_alias
from runepilot.infrastructure.lcu_client import lcu_request


def _positive_int(value: Any) -> int | None:
    """Değeri pozitif int'e çevirir; olmuyorsa None döndürür."""
    try:
        cid = int(value)
    except (TypeError, ValueError):
        return None
    return cid if cid > 0 else None


class ChampionRepo:
    """LCU şampiyon verisi için cache'li erişim noktası."""

    def __init__(self) -> None:
        self._slug_by_id: dict[int, str] = {}
        self._name_by_id: dict[int, str] = {}

    def get_slug_by_id(self, champ_id: int) -> str | None:
        """LCU verisinden champ_id için runes.json slug'ını çözer (cache'li)."""
        if champ_id in self._slug_by_id:
            return self._slug_by_id[champ_id]

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
                if name and cid_int not in self._name_by_id:
                    self._name_by_id[cid_int] = str(name)

                alias = champ.get("alias") or champ.get("name") or ""
                slug = champion_slug_from_alias(str(alias))
                if slug:
                    self._slug_by_id[cid_int] = slug

            return self._slug_by_id.get(champ_id)
        except Exception:
            return None

    def get_name_by_id(self, champ_id: int) -> str | None:
        """LCU verisinden champ_id için görünen şampiyon adını döndürür (cache'li)."""
        if champ_id in self._name_by_id:
            return self._name_by_id[champ_id]
        # slug + name cache'lerini LCU özet verisinden doldur.
        self.get_slug_by_id(champ_id)
        return self._name_by_id.get(champ_id)

    def load_owned_map(self) -> dict[int, dict[str, Any]]:
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

                cid = _positive_int(champ.get("id"))
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
