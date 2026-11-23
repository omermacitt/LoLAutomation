"""Lobby, matchmaking, position preferences and ready check."""

from collections.abc import Callable

from rune_pilot.application.lobby_service import LobbyService
from rune_pilot.application.ports.league_client import LeagueClient
from rune_pilot.domain.automation_settings import AutomationSettings

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
        settings: AutomationSettings,
        should_run: Callable[[], bool],
        wait: Callable[[float], bool] | None,
    ) -> bool:
        """Returns False when cancellation interrupted the step."""
        queue_id = settings.queue_id
        flow_phase = self._lobby.get_gameflow_phase_safe()
        if not should_run():
            return False
        if settings.auto_queue and queue_id:
            # Only try to create lobby / start search in idle/lobby phases.
            if flow_phase in (None, "None", "Lobby"):
                now = self._now()
                if now - self._last_action > QUEUE_ACTION_INTERVAL:
                    if self._lobby.ensure_lobby(queue_id, should_run=should_run, wait=wait):
                        if not should_run():
                            return False
                        # Position preferences require an active lobby.
                        self._set_roles(settings)
                        self._lobby.ensure_matchmaking_searching(should_run=should_run)
                    self._last_action = now
        else:
            # Without auto queue, only set roles (if a lobby exists) and never start search.
            self._set_roles(settings)

        self._accept_ready_check(should_run)
        return True

    def _set_roles(self, settings: AutomationSettings) -> None:
        body: dict[str, str] = {}
        if settings.primary_role:
            body["firstPreference"] = settings.primary_role
        if settings.secondary_role:
            body["secondPreference"] = settings.secondary_role
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
