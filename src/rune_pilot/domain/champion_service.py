"""
RunePilot şampiyon servisi.

Şampiyon ID/slug/isim çözümleme ve normalizasyon işlemleri.
"""

from __future__ import annotations

import re
from typing import Any

from src.rune_pilot.infrastructure.lcu_client import lcu_request

# Cache'ler: LCU'dan okunan veriler burada tutulur.
CHAMP_SLUG_BY_ID: dict[int, str] = {}
CHAMP_NAME_BY_ID: dict[int, str] = {}


def champion_slug_from_alias(alias: str) -> str:
    """
    Must match the slug format used when generating runes.json (see webscrapping.py).
    """
    alias = (alias or "").strip()
    special = {
        "MonkeyKing": "wukong",
        "FiddleSticks": "fiddlesticks",
    }
    if alias in special:
        return special[alias]
    return alias.lower()


def get_champion_slug_by_id(champ_id: int) -> str | None:
    """LCU verisinden champ_id için runes.json slug'ını çözer (cache'li)."""
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
    """LCU verisinden champ_id için görünen şampiyon adını döndürür (cache'li)."""
    if champ_id in CHAMP_NAME_BY_ID:
        return CHAMP_NAME_BY_ID[champ_id]
    # Populate caches (slug+name) from the LCU champion summary.
    get_champion_slug_by_id(champ_id)
    return CHAMP_NAME_BY_ID.get(champ_id)


def normalize_champion_id(value: Any) -> int | None:
    """Kullanıcı/LCU inputunu pozitif champ_id değerine normalize eder."""
    try:
        cid = int(value)
    except (TypeError, ValueError):
        return None
    return cid if cid > 0 else None


def normalize_spell_id(value: Any) -> int | None:
    """Kullanıcı/LCU inputunu pozitif spell_id değerine normalize eder."""
    try:
        sid = int(value)
    except (TypeError, ValueError):
        return None
    return sid if sid > 0 else None
