"""
The persisted user configuration, as a pure model.

`UserConfig.from_raw()` is the single place that understands every historical shape
of `user_config.json`. It never raises: a config file written by an older build — or
a hand-edited one with garbage in it — degrades to defaults field by field rather
than failing the whole load. That forgiveness is deliberate; the alternative is a UI
that refuses to open because one key is malformed.

`to_raw()` returns only the keys this model owns, so a caller can merge them into an
existing file without touching unrelated preference keys.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from rune_pilot.domain.champion_service import normalize_champion_id, spell_id_from_any, unique_champion_slots
from rune_pilot.domain.constants import ROLE_KEYS

RUNE_SLOTS: tuple[str, ...] = ("1", "2", "3")

# Keys UserConfig owns. Anything else in the file belongs to another component and
# must survive a save untouched.
OWNED_KEYS: tuple[str, ...] = (
    "queue_name",
    "primary_role_name",
    "secondary_role_name",
    "custom_summoner_spells",
    "role_champions_ui",
    "role_bans_ui",
    "custom_runes",
    "rune_selection",
    "custom_skins",
)


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _looks_like_legacy_runes(raw: Any) -> bool:
    """
    True when custom_runes is in the pre-preset shape (role -> champId -> page)
    instead of today's (champId -> slot -> page). Role keys at the top level are the
    tell, since champion IDs are always numeric.
    """
    return isinstance(raw, dict) and any(str(k) in ROLE_KEYS for k in raw)


def _migrate_legacy_runes(raw: dict) -> dict[str, dict[str, dict]]:
    """Folds role -> champId -> page into champId -> "1" -> page."""
    migrated: dict[str, dict[str, dict]] = {}
    for _role_key, pages in raw.items():
        for champ_key, page in _as_dict(pages).items():
            cid = normalize_champion_id(champ_key)
            if cid is None or not isinstance(page, dict):
                continue
            migrated.setdefault(str(cid), {}).setdefault("1", page)
    return migrated


def _clean_runes(raw: dict) -> dict[str, dict[str, dict]]:
    """Drops non-numeric champion keys, unknown slots, and non-dict pages."""
    cleaned: dict[str, dict[str, dict]] = {}
    for champ_key, slots in raw.items():
        cid = normalize_champion_id(champ_key)
        if cid is None:
            continue
        slot_map = {
            str(slot_key): page
            for slot_key, page in _as_dict(slots).items()
            if str(slot_key) in RUNE_SLOTS and isinstance(page, dict)
        }
        if slot_map:
            cleaned[str(cid)] = slot_map
    return cleaned


def _clean_rune_selection(raw: Any, custom_runes: dict[str, dict[str, dict]]) -> dict[str, int]:
    """
    Keeps only selections that point at a preset that actually exists. A selection of
    0 ("recommended") is represented by absence, so it is never stored.
    """
    selection: dict[str, int] = {}
    for champ_key, value in _as_dict(raw).items():
        cid = normalize_champion_id(champ_key)
        if cid is None:
            continue
        try:
            slot = int(value)
        except (TypeError, ValueError):
            continue
        if str(slot) not in RUNE_SLOTS:
            continue
        if str(slot) in custom_runes.get(str(cid), {}):
            selection[str(cid)] = slot
    return selection


def _clean_role_champions(raw: Any) -> dict[str, list[int | None]]:
    """role -> [champId | None, ...], preserving empty slots so rows stay aligned."""
    result: dict[str, list[int | None]] = {}
    for role_key, champ_ids in _as_dict(raw).items():
        if str(role_key) not in ROLE_KEYS or not isinstance(champ_ids, (list, tuple)):
            continue
        result[str(role_key)] = unique_champion_slots([normalize_champion_id(cid) for cid in champ_ids])
    return result


def _clean_role_bans(raw: Any) -> dict[str, int | None]:
    return {
        str(role_key): normalize_champion_id(cid)
        for role_key, cid in _as_dict(raw).items()
        if str(role_key) in ROLE_KEYS
    }


def _clean_custom_skins(raw: Any) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for role_key, skins in _as_dict(raw).items():
        if str(role_key) not in ROLE_KEYS:
            continue
        role_map: dict[str, int] = {}
        for champ_key, skin_id in _as_dict(skins).items():
            cid = normalize_champion_id(champ_key)
            if cid is None:
                continue
            try:
                role_map[str(cid)] = int(skin_id)
            except (TypeError, ValueError):
                continue
        if role_map:
            result[str(role_key)] = role_map
    return result


def _clean_summoner_spells(raw: Any) -> dict[str, dict[str, dict[str, int | None]]]:
    """
    role -> champId -> {"spell1Id", "spell2Id"}.

    Older builds wrote the pair as {"spell1", "spell2"} or as a two-item list, and
    stored spells by display name; all of those are read here and normalized away.
    """
    result: dict[str, dict[str, dict[str, int | None]]] = {}
    for role_key, champs in _as_dict(raw).items():
        if str(role_key) not in ROLE_KEYS:
            continue
        role_map: dict[str, dict[str, int | None]] = {}
        for champ_key, entry in _as_dict(champs).items():
            cid = normalize_champion_id(champ_key)
            if cid is None:
                continue
            if isinstance(entry, dict):
                s1 = spell_id_from_any(entry.get("spell1Id", entry.get("spell1")))
                s2 = spell_id_from_any(entry.get("spell2Id", entry.get("spell2")))
            elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                s1 = spell_id_from_any(entry[0])
                s2 = spell_id_from_any(entry[1])
            else:
                continue
            role_map[str(cid)] = {"spell1Id": s1, "spell2Id": s2}
        if role_map:
            result[str(role_key)] = role_map
    return result


def _legacy_spell_defaults(data: dict) -> dict[str, tuple[int | None, int | None]]:
    """
    Per-role spell defaults from builds that stored one spell pair per role
    (role_spells_ui) or a single global pair (spell1_name / spell2_name).

    Returns role -> (spell1Id, spell2Id), with the global pair applied to every role
    that has no per-role entry. An empty result means there is nothing to migrate.
    """
    defaults: dict[str, tuple[int | None, int | None]] = {}

    for role_key, spells in _as_dict(data.get("role_spells_ui")).items():
        if isinstance(spells, dict):
            pair = (spells.get("spell1_name"), spells.get("spell2_name"))
        elif isinstance(spells, (list, tuple)) and len(spells) >= 2:
            pair = (spells[0], spells[1])
        else:
            continue
        defaults[str(role_key)] = (spell_id_from_any(pair[0]), spell_id_from_any(pair[1]))

    if "spell1_name" in data or "spell2_name" in data:
        global_pair = (
            spell_id_from_any(data.get("spell1_name")),
            spell_id_from_any(data.get("spell2_name")),
        )
        for role_key in ROLE_KEYS:
            defaults.setdefault(role_key, global_pair)

    return defaults


class UserConfig(BaseModel):
    """Everything the main window persists between runs."""

    queue_name: str | None = None
    primary_role_name: str | None = None
    secondary_role_name: str | None = None
    # role -> [champId | None] (one entry per champion row)
    role_champions_ui: dict[str, list[int | None]] = Field(default_factory=dict)
    # role -> champId | None
    role_bans_ui: dict[str, int | None] = Field(default_factory=dict)
    # champId(str) -> slot("1"|"2"|"3") -> rune page
    custom_runes: dict[str, dict[str, dict]] = Field(default_factory=dict)
    # champId(str) -> slot(1|2|3); absent means "use the recommended page"
    rune_selection: dict[str, int] = Field(default_factory=dict)
    # role -> champId(str) -> skinId
    custom_skins: dict[str, dict[str, int]] = Field(default_factory=dict)
    # role -> champId(str) -> {"spell1Id", "spell2Id"}
    custom_summoner_spells: dict[str, dict[str, dict[str, int | None]]] = Field(default_factory=dict)

    @classmethod
    def from_raw(cls, data: Any) -> "UserConfig":
        """Parses a raw config dict, migrating any legacy shape it finds."""
        data = _as_dict(data)

        raw_runes = _as_dict(data.get("custom_runes"))
        is_legacy_runes = _looks_like_legacy_runes(raw_runes)
        custom_runes = (
            _migrate_legacy_runes(raw_runes) if is_legacy_runes else _clean_runes(raw_runes)
        )

        rune_selection = _clean_rune_selection(data.get("rune_selection"), custom_runes)
        if is_legacy_runes and "rune_selection" not in data:
            # Legacy pages were always applied, so point every migrated champion at the
            # single preset the migration produced.
            for champ_key in custom_runes:
                rune_selection.setdefault(champ_key, 1)

        role_champions_ui = _clean_role_champions(data.get("role_champions_ui"))
        custom_summoner_spells = _clean_summoner_spells(data.get("custom_summoner_spells"))

        for role_key, (spell1_id, spell2_id) in _legacy_spell_defaults(data).items():
            if role_key not in role_champions_ui:
                continue
            role_map = custom_summoner_spells.setdefault(role_key, {})
            for cid in role_champions_ui[role_key]:
                if cid is None or str(cid) in role_map:
                    continue
                role_map[str(cid)] = {"spell1Id": spell1_id, "spell2Id": spell2_id}
            if not role_map:
                custom_summoner_spells.pop(role_key, None)

        return cls(
            queue_name=_as_str_or_none(data.get("queue_name")),
            primary_role_name=_as_str_or_none(data.get("primary_role_name")),
            secondary_role_name=_as_str_or_none(data.get("secondary_role_name")),
            role_champions_ui=role_champions_ui,
            role_bans_ui=_clean_role_bans(data.get("role_bans_ui")),
            custom_runes=custom_runes,
            rune_selection=rune_selection,
            custom_skins=_clean_custom_skins(data.get("custom_skins")),
            custom_summoner_spells=custom_summoner_spells,
        )

    def to_raw(self) -> dict[str, Any]:
        """The owned keys, ready to be merged into an existing config file."""
        return self.model_dump(include=set(OWNED_KEYS))
