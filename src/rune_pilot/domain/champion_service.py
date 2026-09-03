"""RunePilot champion service — pure normalization and slug helpers (no LCU dependency).

LCU-dependent functions are in application/champion_query.py.
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
    """Normalizes user/LCU input to a positive champion ID."""
    try:
        cid = int(value)
    except (TypeError, ValueError):
        return None
    return cid if cid > 0 else None


def normalize_spell_id(value: Any) -> int | None:
    """Normalizes user/LCU input to a positive spell ID."""
    try:
        sid = int(value)
    except (TypeError, ValueError):
        return None
    return sid if sid > 0 else None
