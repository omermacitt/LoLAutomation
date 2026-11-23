"""Pure role assignment normalization and preset resolution. Missing differs from 0."""

from collections.abc import Mapping
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
    return choose_rune_slot(
        clean_role_rune_selection(config.get("role_rune_selection")),
        config.get("rune_selection"),
        config.get("custom_runes"),
        role,
        champion,
    )


def choose_rune_slot(
    assignments: Mapping[str, Mapping[str, int]],
    legacy: Any,
    custom_runes: Any,
    role: str,
    champion: int,
) -> RuneChoice:
    """Role assignment wins, then the legacy per-champion choice; a missing preset is 0."""
    key = str(champion)
    entries = assignments.get(role, {})
    explicit = key in entries
    slot = entries[key] if explicit else legacy.get(key, 0) if isinstance(legacy, Mapping) else 0
    if type(slot) is not int or slot not in range(4):
        slot = 0
    pages = custom_runes.get(key, {}) if isinstance(custom_runes, Mapping) else {}
    if slot and (not isinstance(pages, dict) or not isinstance(pages.get(str(slot)), dict)):
        return RuneChoice(0, "role" if explicit else "default", missing=True)
    return RuneChoice(slot, "role" if explicit else "default")
