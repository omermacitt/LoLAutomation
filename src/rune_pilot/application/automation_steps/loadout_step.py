"""Summoner spells and skin for the local player's actual champion."""

from collections.abc import Callable
from typing import Any

from rune_pilot.application.automation_state import AutomationProgress
from rune_pilot.application.ports.league_client import LeagueClient
from rune_pilot.domain.champ_select import keyed_entry, local_champion, local_player, resolve_spells
from rune_pilot.domain.champion_service import normalize_champion_id

WRITE_OK = (200, 201, 204)


class LoadoutStep:
    def __init__(self, client: LeagueClient) -> None:
        self._client = client

    def run(
        self,
        session: dict[str, Any],
        cfg: dict[str, Any],
        role: str,
        handoff_active: bool,
        progress: AutomationProgress,
        should_run: Callable[[], bool],
    ) -> bool:
        """Returns False when cancellation interrupted the step."""
        loadout_role = role or str(cfg.get("primary_role", "")).upper()
        champion = local_champion(session)
        # A handed-off hover is the player's decision in progress; wait for the lock.
        if handoff_active and not normalize_champion_id(local_player(session).get("championId")):
            champion = 0

        spell1, spell2 = resolve_spells(cfg, loadout_role, champion)
        if champion and (spell1 or spell2):
            body = {}
            if spell1:
                body["spell1Id"] = spell1
            if spell2:
                body["spell2Id"] = spell2
            self._client.set_selection(body)

        if not should_run():
            return False
        try:
            self._apply_skin(cfg, loadout_role, champion, progress)
        except Exception as e:
            print(f"[SKIN] Failed to apply skin: {e}")
        return True

    def _apply_skin(
        self, cfg: dict[str, Any], role: str, champion: int, progress: AutomationProgress
    ) -> None:
        if not champion:
            progress.skin_key = None
            return
        skin_id = champion * 1000  # The default skin.
        try:
            skin_id = int(keyed_entry(cfg.get("custom_skins"), role, champion))
        except (TypeError, ValueError):
            pass
        skin_key = (champion, skin_id)
        if progress.skin_key != skin_key:
            reply = self._client.set_selection({"selectedSkinId": skin_id})
            if reply.status_code in WRITE_OK:
                progress.skin_key = skin_key
