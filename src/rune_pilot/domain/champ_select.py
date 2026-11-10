"""Pure champion-select availability and spell normalization rules."""

from typing import Any

from rune_pilot.domain.champion_service import normalize_spell_id
from rune_pilot.domain.champion_service import normalize_champion_id
from rune_pilot.shared.utils import safe_int_list


def pick_candidates(session: dict, preferences: list, pickable_ids: set[int] | None) -> list[int]:
    """Keep preference order, excluding unavailable, banned or already picked champions."""
    candidates = [cid for value in preferences if (cid := normalize_champion_id(value)) is not None]
    if pickable_ids is not None:
        candidates = [cid for cid in candidates if cid in pickable_ids]
    return [cid for cid in candidates if not is_banned(session, cid) and not is_picked(session, cid)]


def local_player(session: dict) -> dict:
    return next((player for player in session.get('myTeam', []) if isinstance(player, dict)
                 and player.get('cellId') == session.get('localPlayerCellId')), {})


def open_pick_action(session: dict, *, active_only: bool = True) -> dict | None:
    return next((action for group in session.get('actions', []) if isinstance(group, list)
                 for action in group if isinstance(action, dict) and action.get('type') == 'pick'
                 and action.get('actorCellId') == session.get('localPlayerCellId')
                 and not action.get('completed') and (not active_only or action.get('isInProgress') is not False)), None)


def spell_fallbacks(config: dict, role: str, champion_id: int) -> tuple[Any, bool]:
    """First-preference-derived defaults must not leak to a replacement champion."""
    pools = config.get('role_champions') or {}
    role_map = config.get('role_summoner_spells') or {}
    entry = role_map.get(role) if isinstance(role_map, dict) else None
    if not pools:  # Older API clients may supply explicit generic spell pairs.
        return entry, True
    preferences = safe_int_list(pools.get(role))
    primary = str(config.get('primary_role') or '').upper()
    primary_preferences = safe_int_list(pools.get(primary))
    role_matches = bool(preferences and preferences[0] == champion_id)
    global_matches = bool(role == primary and primary_preferences and primary_preferences[0] == champion_id)
    return entry if role_matches else None, global_matches


def is_banned(session: dict[str, Any], champ_id: int) -> bool:
    """Returns True if the given champion ID is banned in the current champ-select session."""
    bans = session.get("bans") or {}
    if not isinstance(bans, dict):
        return False

    all_bans_raw = (bans.get("myTeamBans") or []) + (bans.get("theirTeamBans") or [])
    all_bans = set(safe_int_list(all_bans_raw))
    try:
        champ_id_int = int(champ_id)
    except (TypeError, ValueError):
        return False
    return champ_id_int in all_bans


def is_picked(session: dict[str, Any], champ_id: int) -> bool:
    """Returns True if the given champion ID is already picked in the current session."""
    try:
        champ_id_int = int(champ_id)
    except (TypeError, ValueError):
        return False

    for team_key in ("myTeam", "theirTeam"):
        for player in session.get(team_key, []) or []:
            if not isinstance(player, dict):
                continue
            try:
                picked = int(player.get("championId") or 0)
            except (TypeError, ValueError):
                picked = 0
            if picked == champ_id_int and champ_id_int != 0:
                return True

    return False


def is_teammate_showing(session: dict[str, Any], champ_id: int) -> bool:
    """Returns True if a teammate is hovering or intending to pick the given champion."""
    try:
        cid = int(champ_id)
    except (TypeError, ValueError):
        return False

    for p in session.get("myTeam", []):
        if not isinstance(p, dict):
            continue
        try:
            shown = int(p.get("championId") or 0)
        except (TypeError, ValueError):
            shown = 0
        if shown == cid and cid != 0:
            return True

        try:
            intent = int(p.get("championPickIntent") or 0)
        except (TypeError, ValueError):
            intent = 0
        if intent == cid and cid != 0:
            return True

    return False


def extract_spell_pair(entry: Any) -> tuple[bool, int | None, bool, int | None]:
    """
    Resolves a summoner spell pair from various input formats.

    Returns: (has_spell1, spell1_id, has_spell2, spell2_id)
    """
    has_s1 = False
    has_s2 = False
    s1: int | None = None
    s2: int | None = None

    if isinstance(entry, dict):
        if "spell1Id" in entry or "spell1" in entry:
            has_s1 = True
        if "spell2Id" in entry or "spell2" in entry:
            has_s2 = True

        if "spell1Id" in entry:
            s1 = normalize_spell_id(entry.get("spell1Id"))
        elif "spell1" in entry:
            s1 = normalize_spell_id(entry.get("spell1"))

        if "spell2Id" in entry:
            s2 = normalize_spell_id(entry.get("spell2Id"))
        elif "spell2" in entry:
            s2 = normalize_spell_id(entry.get("spell2"))
    elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
        has_s1 = True
        has_s2 = True
        s1 = normalize_spell_id(entry[0])
        s2 = normalize_spell_id(entry[1])

    return has_s1, s1, has_s2, s2
