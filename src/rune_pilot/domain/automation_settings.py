"""
Typed, read-only view of one automation settings snapshot.

`AutomationConfig` validates HTTP input; the automation worker still receives plain
dictionaries (including partial ones from older clients and tests). This view parses
such a dictionary once per loop iteration with the worker's historical tolerance:
missing values stay missing instead of taking HTTP defaults.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from rune_pilot.domain.champion_service import normalize_champion_id, normalize_spell_id
from rune_pilot.domain.rune_selection import RuneChoice, choose_rune_slot, clean_role_rune_selection

RECOMMENDATION_QUEUES = (400, 420, 440)


def _role(value: Any) -> str:
    return str(value).upper() if value else ""


def _queue_id(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def _champion_keyed(value: Any) -> dict[str, dict[str, Any]]:
    """role -> champion -> entry with string champion keys; string keys beat legacy int keys."""
    result: dict[str, dict[str, Any]] = {}
    for role, entries in _mapping(value).items():
        if not isinstance(entries, Mapping):
            continue
        merged = {k: v for k, v in entries.items() if isinstance(k, str) and v is not None}
        for k, v in entries.items():
            if not isinstance(k, str):
                merged.setdefault(str(k), v)
        result[role] = merged
    return result


@dataclass(frozen=True)
class AutomationSettings:
    primary_role: str = ""
    secondary_role: str = ""
    auto_queue: bool = True
    queue_id: int | None = None
    recommendations_enabled: bool = True
    role_bans: Mapping[str, int] = field(default_factory=dict)
    # Champion slots keep their saved values; the pick service filters invalid entries.
    role_champions: Mapping[str, tuple[Any, ...]] = field(default_factory=dict)
    primary_spell: int | None = None
    secondary_spell: int | None = None
    role_spells: Mapping[str, Any] = field(default_factory=dict)
    champion_spells: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    champion_skins: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    custom_runes: Mapping[str, Any] = field(default_factory=dict)
    role_rune_selection: Mapping[str, Mapping[str, int]] = field(default_factory=dict)
    legacy_rune_selection: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "AutomationSettings":
        bans = {}
        for role, champion in _mapping(raw.get("role_bans")).items():
            if (champion_id := normalize_champion_id(champion)) is not None:
                bans[role] = champion_id
        pools = {
            role: tuple(values) if isinstance(values, (list, tuple)) else ()
            for role, values in _mapping(raw.get("role_champions")).items()
        }
        return cls(
            primary_role=_role(raw.get("primary_role")),
            secondary_role=_role(raw.get("secondary_role")),
            auto_queue=bool(raw.get("auto_queue", True)),
            queue_id=_queue_id(raw.get("queue_id")),
            # Without a queue the worker historically assumed a draft queue (400).
            recommendations_enabled=raw.get("queue_id", 400) in RECOMMENDATION_QUEUES,
            role_bans=bans,
            role_champions=pools,
            primary_spell=normalize_spell_id(raw.get("primary_summoner_spell")),
            secondary_spell=normalize_spell_id(raw.get("secondary_summoner_spell")),
            role_spells=_mapping(raw.get("role_summoner_spells")),
            champion_spells=_champion_keyed(raw.get("custom_summoner_spells")),
            champion_skins=_champion_keyed(raw.get("custom_skins")),
            custom_runes=_mapping(raw.get("custom_runes")),
            role_rune_selection=clean_role_rune_selection(raw.get("role_rune_selection")),
            legacy_rune_selection=_mapping(raw.get("rune_selection")),
        )

    def effective_role(self, assigned: str) -> str:
        """The assigned position, or the primary role in queues without positions."""
        return assigned or self.primary_role

    def ban_for(self, assigned: str) -> int | None:
        return self.role_bans.get(assigned) if assigned else self.role_bans.get(self.primary_role)

    def preferences_for(self, assigned: str) -> tuple[Any, ...]:
        return self.role_champions.get(self.effective_role(assigned), ())

    def champion_spell_entry(self, role: str, champion_id: int) -> Any:
        return self.champion_spells.get(role, {}).get(str(champion_id))

    def champion_skin(self, role: str, champion_id: int) -> Any:
        return self.champion_skins.get(role, {}).get(str(champion_id))

    def rune_choice(self, role: str, champion_id: int) -> RuneChoice:
        return choose_rune_slot(
            self.role_rune_selection,
            self.legacy_rune_selection,
            self.custom_runes,
            role,
            champion_id,
        )

    def custom_rune_page(self, champion_id: int, slot: int) -> Any:
        presets = self.custom_runes.get(str(champion_id))
        return presets.get(str(slot)) if isinstance(presets, Mapping) else None
