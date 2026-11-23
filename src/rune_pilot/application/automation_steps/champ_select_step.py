"""Ban and pick decisions, including the manual-control handoff latch."""

from collections.abc import Callable
from typing import Any

from rune_pilot.application.lobby_service import LobbyService
from rune_pilot.application.selection_feedback import SelectionFeedback
from rune_pilot.domain.automation_settings import AutomationSettings
from rune_pilot.domain.champ_select import local_player, open_pick_action
from rune_pilot.domain.champion_service import normalize_champion_id

# Pick results that hand the current pick action over to the player.
HANDOFF_STATUSES = frozenset(
    {"no_preference", "all_unavailable", "pick_failed", "manual_hover", "manual_selection"}
)


class ChampSelectStep:
    """Owns one invocation's handoff latch; create a fresh step for every loop run."""

    def __init__(self, lobby: LobbyService, feedback: SelectionFeedback) -> None:
        self._lobby = lobby
        self._feedback = feedback
        self.handoff_key: tuple | None = None

    def reset(self) -> None:
        """A missing session ends the handoff and its notice."""
        self.handoff_key = None

    def run(
        self,
        session: dict[str, Any],
        settings: AutomationSettings,
        role: str,
        should_run: Callable[[], bool],
    ) -> bool:
        """Returns False when cancellation interrupted the step."""
        ban_id = settings.ban_for(role)
        if ban_id is not None:
            self._lobby.do_ban(session, ban_id, should_run=should_run)
        preferences = list(settings.preferences_for(role))

        player = local_player(session)
        action = open_pick_action(session, active_only=False)
        action_key = (
            (session.get("gameId"), session.get("localPlayerCellId"), action.get("id"))
            if action
            else None
        )
        if normalize_champion_id(player.get("championId")):
            self._feedback.clear()
        elif action_key is not None:
            if self.handoff_key != action_key:
                self.handoff_key = None
                result = self._pick(session, action, player, preferences, should_run)
                if not should_run():
                    return False
                status = result.get("status")
                if status in HANDOFF_STATUSES:
                    self.handoff_key = action_key
                    self._feedback.publish(
                        action_key,
                        "manual_hover" if status == "manual_selection" else status,
                        settings.effective_role(role),
                        normalize_champion_id(player.get("championPickIntent")),
                    )
                else:
                    self._feedback.clear()
        elif self.handoff_key is None:
            self._feedback.clear()
        return True

    def _pick(
        self,
        session: dict[str, Any],
        action: dict,
        player: dict,
        preferences: list,
        should_run: Callable[[], bool],
    ) -> dict[str, Any]:
        if not preferences:
            return {"status": "no_preference"}
        if normalize_champion_id(player.get("championPickIntent")):
            return {"status": "manual_hover"}
        if action.get("isInProgress") is False:
            return {"status": "no_pick_available"}
        return self._lobby.auto_pick_impl(session, preferences, should_run=should_run)
