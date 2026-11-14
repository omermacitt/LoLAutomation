"""Prefer the requested position, then accept the same champion's client fallback."""

from typing import Any

from rune_pilot.domain.constants import ROLE_KEYS


def recommendation_pages(raw: Any, champion_id: int, role: str) -> list[dict]:
    if role not in ROLE_KEYS or not isinstance(raw, list):
        return []
    candidates = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if not isinstance(item.get("position"), str):
            continue
        if (
            item.get("recommendationChampionId") != champion_id
            or item.get("position") not in ROLE_KEYS
        ):
            continue
        perks = item.get("perks")
        if not isinstance(perks, list):
            continue
        candidates.append(
            {
                "sourceRole": item["position"],
                "name": "League",
                "primaryStyleId": item.get("primaryPerkStyleId"),
                "subStyleId": item.get("secondaryPerkStyleId"),
                "selectedPerkIds": [p.get("id") if isinstance(p, dict) else None for p in perks],
            }
        )
    exact = [page for page in candidates if page["sourceRole"] == role]
    return exact + [page for page in candidates if page["sourceRole"] != role]
