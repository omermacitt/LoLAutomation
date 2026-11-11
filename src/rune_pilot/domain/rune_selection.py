"""Pure role assignment normalization and preset resolution. Missing differs from 0."""

from dataclasses import dataclass
from typing import Any

from rune_pilot.domain.champion_service import normalize_champion_id
from rune_pilot.domain.constants import ROLE_KEYS


def clean_role_rune_selection(raw: Any) -> dict[str, dict[str, int]]:
    result = {}
    if not isinstance(raw, dict):
        return result
    for role, entries in raw.items():
        if role not in ROLE_KEYS or not isinstance(entries, dict):
            continue
        choices = {}
        for key, value in entries.items():
            champion = normalize_champion_id(key)
            if champion is not None:
                choices[str(champion)] = value if type(value) is int and value in range(4) else 0
        if choices:
            result[role] = choices
    return result


@dataclass(frozen=True)
class RuneChoice:
    slot: int
    source: str
    missing: bool = False


def resolve_rune_choice(config: dict, role: str, champion: int) -> RuneChoice:
    key = str(champion)
    assignments = clean_role_rune_selection(config.get("role_rune_selection"))
    entries = assignments.get(role, {})
    explicit = key in entries
    legacy = config.get("rune_selection")
    slot = entries[key] if explicit else legacy.get(key, 0) if isinstance(legacy, dict) else 0
    if type(slot) is not int or slot not in range(4):
        slot = 0
    pages = config.get("custom_runes")
    pages = pages.get(key, {}) if isinstance(pages, dict) else {}
    if slot and (not isinstance(pages, dict) or not isinstance(pages.get(str(slot)), dict)):
        return RuneChoice(0, "role" if explicit else "default", missing=True)
    return RuneChoice(slot, "role" if explicit else "default")
