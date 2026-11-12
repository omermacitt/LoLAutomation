"""Extract only the requested champion/position from client recommendations."""

from typing import Any

from rune_pilot.domain.constants import ROLE_KEYS


def recommendation_pages(raw: Any, champion_id: int, role: str) -> list[dict]:
    # LCU may return default TOP pages even for a successful JUNGLE/MIDDLE request.
    # Neither HTTP 200 nor isDefaultPosition proves that a page matches the role.
    if role not in ROLE_KEYS or not isinstance(raw, list):
        return []
    pages = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if item.get("recommendationChampionId") != champion_id or item.get("position") != role:
            continue
        perks = item.get("perks")
        if not isinstance(perks, list):
            continue
        pages.append(
            {
                "name": "League",
                "primaryStyleId": item.get("primaryPerkStyleId"),
                "subStyleId": item.get("secondaryPerkStyleId"),
                "selectedPerkIds": [p.get("id") if isinstance(p, dict) else None for p in perks],
            }
        )
    return pages
