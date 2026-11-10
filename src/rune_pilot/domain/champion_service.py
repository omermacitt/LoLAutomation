"""RunePilot champion service — pure normalization and slug helpers (no LCU dependency).

LCU-dependent functions are in application/champion_query.py.
"""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping, Sequence

from rune_pilot.domain.constants import SUMMONER_SPELLS


class DuplicateChampionChoices(ValueError):
    """One role cannot contain the same nonempty champion more than once."""


def unique_champion_slots(slots: Sequence[int | None]) -> list[int | None]:
    """Keep the first occurrence and leave later duplicate positions empty."""
    seen: set[int] = set()
    result: list[int | None] = []
    for cid in slots:
        result.append(None if cid is not None and cid in seen else cid)
        if cid is not None:
            seen.add(cid)
    return result


def ensure_unique_role_champions(choices: Mapping[str, Sequence[int | None]]) -> None:
    for slots in choices.values():
        if list(slots) != unique_champion_slots(slots):
            raise DuplicateChampionChoices("A champion can only be selected once per role")


def is_mode_champion_variant(champion: dict[str, Any]) -> bool:
    """Exclude League Classic's Jade roster from our draft/ranked queues.

    Localized names overlap with regular champions. Use mode metadata rather
    than display names or an arbitrary numeric ID cutoff.
    """
    return str(champion.get("alias") or "").strip().casefold().startswith("jade_")


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


def spell_id_from_any(value: Any) -> int | None:
    """
    Normalizes a summoner spell written either as a display name ("Flash") or as a
    raw ID (4, "4") to a positive spell ID.

    Older config files stored spells by name, so both forms have to be readable.
    """
    if value is None:
        return None
    if isinstance(value, str) and value in SUMMONER_SPELLS:
        return SUMMONER_SPELLS[value]
    return normalize_spell_id(value)
