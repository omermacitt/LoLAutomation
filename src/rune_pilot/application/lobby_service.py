"""Lobby/selection orchestration through the injected League Client."""

import time
from collections.abc import Callable
from typing import Any

from rune_pilot.application.ports.league_client import LeagueClient
from rune_pilot.application.champion_query import ChampionQuery
from rune_pilot.domain.champ_select import is_teammate_showing, pick_candidates, local_player, open_pick_action


class LobbyService:
    def __init__(self, client: LeagueClient, champions: ChampionQuery, *, sleep: Callable[[float], None] = time.sleep):
        self._client = client
        self._champions = champions
        self._sleep = sleep
        self._last_ban_skip: tuple[int, int] | None = None

    def do_ban(self, session: dict[str, Any], champ_id: int, *, should_run: Callable[[], bool] = lambda: True) -> None:
        """Attempts to ban the given champion if the player's ban action is open."""
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

                    if key is not None and self._last_ban_skip != key:
                        champ_name = self._champions.get_champion_name_by_id(int(champ_id)) or str(champ_id)
                        print(
                            f"[BAN] Skipping ban for {champ_name} ({champ_id}) because a teammate is showing it"
                        )
                        self._last_ban_skip = key
                    return

                self._last_ban_skip = None
                if not should_run():
                    return
                try:
                    self._client.complete_action(action_id, champ_id)
                except Exception as e:
                    print(f"[BAN] Failed to ban championId={champ_id}: {e}")
                return

    def get_pickable_champion_ids(self) -> set[int] | None:
        """
        Returns the set of champion ids the player can currently pick in champ select.
        If the endpoint isn't available (not in champ select, etc.), returns None.
        """
        try:
            res = self._client.pickable_champion_ids()
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

    def auto_pick_impl(self, session: dict[str, Any], champion_ids: list[int], *, should_run: Callable[[], bool] = lambda: True) -> dict[str, Any]:
        """
        Tries to pick the first available champion from the preference list.

        The order of `champion_ids` matters; the first eligible champion is attempted.
        """
        player = local_player(session)
        if player.get('championId') or player.get('championPickIntent'):
            return {'status': 'manual_selection'}
        action = open_pick_action(session)
        if action is None:
            return {'status': 'no_pick_available'}
        action_id = action.get('id')
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

        pickable_ids = self.get_pickable_champion_ids()
        if not should_run():
            return {"status": "cancelled"}
        candidate_ids = pick_candidates(session, valid_ids, pickable_ids)

        if not candidate_ids:
            print(f"[AUTO-PICK] No pickable preferred champions. preferred={valid_ids}")
            return {"status": "all_unavailable", "attempted": valid_ids}

        if action_id is None:
            return {"status": "no_pick_available"}

        last_error = None
        for champ_to_pick in candidate_ids:
            if not should_run():
                return {"status": "cancelled"}
            print(f"[AUTO-PICK] Picking champion {champ_to_pick}")
            try:
                res = self._client.complete_action(action_id, champ_to_pick)
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

    def get_gameflow_phase_safe(self) -> str | None:
        """Reads the LCU gameflow phase; returns `None` on error."""
        try:
            res = self._client.gameflow_phase()
            if res.status_code != 200:
                return None
            phase = res.json()
            if isinstance(phase, str):
                return phase
            return None
        except Exception:
            return None

    def ensure_lobby(self, queue_id: int, *, should_run: Callable[[], bool] = lambda: True,
                     wait: Callable[[float], bool] | None = None) -> bool:
        """Ensures a lobby with the given queue ID exists, creating one if necessary. Returns True on success."""
        try:
            res = self._client.lobby()
            if not should_run():
                return False
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
                self._client.delete_lobby()
                (wait if wait is not None else self._sleep)(0.5)
        except Exception:
            pass

        if not should_run():
            return False
        try:
            create_res = self._client.create_lobby(queue_id)
            if create_res.status_code in (200, 201, 204):
                print(f"[QUEUE] Lobby created queueId={queue_id}")
                return True
            print(f"[QUEUE] Failed to create lobby: {create_res.status_code} {create_res.text}")
        except Exception as e:
            print(f"[QUEUE] Error creating lobby: {e}")

        return False

    def ensure_matchmaking_searching(self, *, should_run: Callable[[], bool] = lambda: True) -> None:
        """Starts matchmaking search if it is not already searching."""
        try:
            state_res = self._client.matchmaking_search_state()
            if state_res.status_code == 200:
                state = state_res.json()
                if isinstance(state, dict) and state.get("searchState") == "Searching":
                    return
        except Exception:
            # Some client versions may not expose the search-state endpoint.
            pass

        if not should_run():
            return
        try:
            res = self._client.start_matchmaking()
            if res.status_code in (200, 204):
                print("[QUEUE] Matchmaking search started")
                return
            print(f"[QUEUE] Failed to start search: {res.status_code} {res.text}")
        except Exception as e:
            print(f"[QUEUE] Error starting search: {e}")
