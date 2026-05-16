"""
RunePilot şampiyon servisi.

Saf normalizasyon ve slug çözümleme yardımcıları (LCU bağımlılığı yok).
LCU'ya bağımlı fonksiyonlar application/champion_query.py içinde tanımlanmıştır.
"""

from __future__ import annotations

from typing import Any


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
