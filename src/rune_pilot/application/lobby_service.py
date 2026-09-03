"""RunePilot lobby and queue management service — lobby creation, matchmaking, ban, and champion pick."""

from __future__ import annotations

import time
from typing import Any

from rune_pilot.infrastructure.lcu_client import lcu_request
from rune_pilot.domain.champion_service import normalize_champion_id, normalize_spell_id
from rune_pilot.application.champion_query import get_champion_name_by_id
from rune_pilot.shared.utils import safe_int_list

LAST_BAN_SKIP: tuple[int, int] | None = None


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


def do_ban(session: dict[str, Any], champ_id: int) -> None:
    """Attempts to ban the given champion if the player's ban action is open."""
    global LAST_BAN_SKIP
    my_cell = session.get("localPlayerCellId")

    for group in session.get("actions", []) or []:
        if not isinstance(group, list):
            continue
        for action in group:
            if not isinstance(action, dict):
                continue
            if action.get("type") != "ban":
                continue
            if action.get("actorCellId") != my_cell:
                continue
            if action.get("completed"):
                continue

            action_id = action.get("id")
            if is_teammate_showing(session, champ_id):
                try:
                    key = (int(action_id), int(champ_id))
                except (TypeError, ValueError):
                    key = None

                if key is not None and LAST_BAN_SKIP != key:
                    champ_name = get_champion_name_by_id(int(champ_id)) or str(champ_id)
                    print(
                        f"[BAN] Skipping ban for {champ_name} ({champ_id}) because a teammate is showing it"
                    )
                    LAST_BAN_SKIP = key
                return

            LAST_BAN_SKIP = None
            try:
                lcu_request(
                    "PATCH",
                    f"/lol-champ-select/v1/session/actions/{action_id}",
                    {"championId": champ_id, "completed": True},
                )
            except Exception as e:
                print(f"[BAN] Failed to ban championId={champ_id}: {e}")
            return


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


def get_pickable_champion_ids() -> set[int] | None:
    """
    Returns the set of champion ids the player can currently pick in champ select.
    If the endpoint isn't available (not in champ select, etc.), returns None.
    """
    try:
        res = lcu_request("GET", "/lol-champ-select/v1/pickable-champion-ids")
        if res.status_code != 200:
            return None

        ids = res.json()
        if not isinstance(ids, list):
            return None

        pickable: set[int] = set()
        for cid in ids:
            try:
                cid_int = int(cid)
            except (TypeError, ValueError):
                continue
            if cid_int > 0:
                pickable.add(cid_int)
        return pickable
    except Exception as e:
        print(f"[AUTO-PICK] Error fetching pickable champion ids: {e}")
        return None


def auto_pick_impl(session: dict[str, Any], champion_ids: list[int]) -> dict[str, Any]:
    """
    Tries to pick the first available champion from the preference list.

    The order of `champion_ids` matters; the first eligible champion is attempted.
    """
    valid_ids: list[int] = []
    for c in champion_ids:
        try:
            cid = int(c)
        except (TypeError, ValueError):
            continue
        if cid > 0:
            valid_ids.append(cid)

    if not valid_ids:
        return {"status": "no_preference"}

    pickable_ids = get_pickable_champion_ids()
    candidate_ids = valid_ids
    if pickable_ids is not None:
        candidate_ids = [cid for cid in candidate_ids if cid in pickable_ids]

    candidate_ids = [cid for cid in candidate_ids if not is_banned(session, cid) and not is_picked(session, cid)]

    if not candidate_ids:
        print(f"[AUTO-PICK] No pickable preferred champions. preferred={valid_ids}")
        return {"status": "all_unavailable", "attempted": valid_ids}

    my_cell = session.get("localPlayerCellId")
    action_id = None
    for group in session.get("actions", []):
        for action in group:
            if (
                action.get("type") == "pick"
                and action.get("actorCellId") == my_cell
                and not action.get("completed")
            ):
                action_id = action.get("id")
                break
        if action_id is not None:
            break

    if action_id is None:
        return {"status": "no_pick_available"}

    last_error = None
    for champ_to_pick in candidate_ids:
        print(f"[AUTO-PICK] Picking champion {champ_to_pick}")
        try:
            res = lcu_request(
                "PATCH",
                f"/lol-champ-select/v1/session/actions/{action_id}",
                {"championId": champ_to_pick, "completed": True},
            )
            if res.status_code in (200, 204):
                return {"status": "picked", "champion": champ_to_pick}

            last_error = {
                "champion": champ_to_pick,
                "status_code": res.status_code,
                "body": res.text,
            }
            print(f"[AUTO-PICK] Pick failed for {champ_to_pick}: {res.status_code} {res.text}")
        except Exception as e:
            last_error = {"champion": champ_to_pick, "error": str(e)}
            print(f"[AUTO-PICK] Pick error for {champ_to_pick}: {e}")

    return {"status": "pick_failed", "attempted": candidate_ids, "last_error": last_error}


def get_gameflow_phase_safe() -> str | None:
    """Reads the LCU gameflow phase; returns `None` on error."""
    try:
        res = lcu_request("GET", "/lol-gameflow/v1/gameflow-phase")
        if res.status_code != 200:
            return None
        phase = res.json()
        if isinstance(phase, str):
            return phase
        return None
    except Exception:
        return None


def ensure_lobby(queue_id: int) -> bool:
    """Ensures a lobby with the given queue ID exists, creating one if necessary. Returns True on success."""
    try:
        res = lcu_request("GET", "/lol-lobby/v2/lobby")
        if res.status_code == 200:
            lobby = res.json()
            current_queue = None
            try:
                current_queue = int((lobby.get("gameConfig") or {}).get("queueId"))
            except Exception:
                current_queue = None

            if current_queue == queue_id:
                return True

            # Wrong queue: leave and recreate.
            lcu_request("DELETE", "/lol-lobby/v2/lobby")
            time.sleep(0.5)
    except Exception:
        pass

    try:
        create_res = lcu_request("POST", "/lol-lobby/v2/lobby", {"queueId": int(queue_id)})
        if create_res.status_code in (200, 201, 204):
            print(f"[QUEUE] Lobby created queueId={queue_id}")
            return True
        print(f"[QUEUE] Failed to create lobby: {create_res.status_code} {create_res.text}")
    except Exception as e:
        print(f"[QUEUE] Error creating lobby: {e}")

    return False


def ensure_matchmaking_searching() -> None:
    """Starts matchmaking search if it is not already searching."""
    try:
        state_res = lcu_request("GET", "/lol-lobby/v2/lobby/matchmaking/search-state")
        if state_res.status_code == 200:
            state = state_res.json()
            if isinstance(state, dict) and state.get("searchState") == "Searching":
                return
    except Exception:
        # Some client versions may not expose the search-state endpoint.
        pass

    try:
        res = lcu_request("POST", "/lol-lobby/v2/lobby/matchmaking/search")
        if res.status_code in (200, 204):
            print("[QUEUE] Matchmaking search started")
            return
        print(f"[QUEUE] Failed to start search: {res.status_code} {res.text}")
    except Exception as e:
        print(f"[QUEUE] Error starting search: {e}")
