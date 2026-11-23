"""Lobby, matchmaking, position preferences and ready check."""

from collections.abc import Callable
from typing import Any

from rune_pilot.application.lobby_service import LobbyService
from rune_pilot.application.ports.league_client import LeagueClient

QUEUE_ACTION_INTERVAL = 5


class QueueStep:
    """Owns one invocation's queue throttle; create a fresh step for every loop run."""

    def __init__(self, client: LeagueClient, lobby: LobbyService, now: Callable[[], float]) -> None:
        self._client = client
        self._lobby = lobby
        self._now = now
        self._last_action = 0.0

    def run(
        self,
        cfg: dict[str, Any],
        should_run: Callable[[], bool],
        wait: Callable[[float], bool] | None,
    ) -> bool:
        """Returns False when cancellation interrupted the step."""
        auto_queue = bool(cfg.get("auto_queue", True))
        queue_id = cfg.get("queue_id")
        try:
            queue_id = int(queue_id) if queue_id is not None else None
        except Exception:
            queue_id = None

        flow_phase = self._lobby.get_gameflow_phase_safe()
        if not should_run():
            return False
        if auto_queue and queue_id:
            # Only try to create lobby / start search in idle/lobby phases.
            if flow_phase in (None, "None", "Lobby"):
                now = self._now()
                if now - self._last_action > QUEUE_ACTION_INTERVAL:
                    if self._lobby.ensure_lobby(queue_id, should_run=should_run, wait=wait):
                        if not should_run():
                            return False
                        # Position preferences require an active lobby.
                        self._set_roles(cfg)
                        self._lobby.ensure_matchmaking_searching(should_run=should_run)
                    self._last_action = now
        else:
            # Without auto queue, only set roles (if a lobby exists) and never start search.
            self._set_roles(cfg)

        self._accept_ready_check(should_run)
        return True

    def _set_roles(self, cfg: dict[str, Any]) -> None:
        body: dict[str, str] = {}
        if cfg.get("primary_role"):
            body["firstPreference"] = str(cfg["primary_role"]).upper()
        if cfg.get("secondary_role"):
            body["secondPreference"] = str(cfg["secondary_role"]).upper()
        if body:
            self._client.set_position_preferences(body)

    def _accept_ready_check(self, should_run: Callable[[], bool]) -> None:
        try:
            reply = self._client.ready_check()
            if reply.status_code == 200 and reply.json().get("state") == "InProgress":
                if should_run():
                    self._client.accept_ready_check()
        except Exception:
            pass
