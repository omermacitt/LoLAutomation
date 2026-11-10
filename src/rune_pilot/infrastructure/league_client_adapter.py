"""Translate League operations into authenticated LCU HTTP requests."""

from collections.abc import Callable

from rune_pilot.application.ports.league_client import ClientReply
from rune_pilot.infrastructure.lcu_client import lcu_request


class LcuLeagueClient:
    def __init__(self, request: Callable = lcu_request):
        self._request = request

    def champion_summary(self) -> ClientReply:
        return self._request("GET", "/lol-game-data/assets/v1/champion-summary.json")

    def owned_champions(self) -> ClientReply:
        return self._request("GET", "/lol-champions/v1/owned-champions-minimal")

    def champion_data(self, champion_id: int) -> ClientReply:
        return self._request("GET", f"/lol-game-data/assets/v1/champions/{int(champion_id)}.json")

    def skin_inventory(self) -> ClientReply:
        return self._request("GET", "/lol-inventory/v2/inventory/CHAMPION_SKIN")

    def perk_styles(self) -> ClientReply:
        return self._request("GET", "/lol-perks/v1/styles")

    def perks(self, *, game_data: bool = False) -> ClientReply:
        endpoint = "/lol-game-data/assets/v1/perks.json" if game_data else "/lol-perks/v1/perks"
        return self._request("GET", endpoint)

    def asset(self, path: str) -> ClientReply:
        return self._request("GET", path)

    def gameflow_phase(self) -> ClientReply:
        return self._request("GET", "/lol-gameflow/v1/gameflow-phase")

    def lobby(self) -> ClientReply:
        return self._request("GET", "/lol-lobby/v2/lobby")

    def delete_lobby(self) -> ClientReply:
        return self._request("DELETE", "/lol-lobby/v2/lobby")

    def create_lobby(self, queue_id: int) -> ClientReply:
        return self._request("POST", "/lol-lobby/v2/lobby", {"queueId": int(queue_id)})

    def set_position_preferences(self, preferences: dict) -> ClientReply:
        return self._request(
            "PUT", "/lol-lobby/v2/lobby/members/localMember/position-preferences", preferences
        )

    def matchmaking_search_state(self) -> ClientReply:
        return self._request("GET", "/lol-lobby/v2/lobby/matchmaking/search-state")

    def start_matchmaking(self) -> ClientReply:
        return self._request("POST", "/lol-lobby/v2/lobby/matchmaking/search")

    def ready_check(self) -> ClientReply:
        return self._request("GET", "/lol-matchmaking/v1/ready-check")

    def accept_ready_check(self) -> ClientReply:
        return self._request("POST", "/lol-matchmaking/v1/ready-check/accept")

    def champ_select_session(self) -> ClientReply:
        return self._request("GET", "/lol-champ-select/v1/session")

    def pickable_champion_ids(self) -> ClientReply:
        return self._request("GET", "/lol-champ-select/v1/pickable-champion-ids")

    def complete_action(self, action_id: int, champion_id: int) -> ClientReply:
        return self._request(
            "PATCH",
            f"/lol-champ-select/v1/session/actions/{action_id}",
            {"championId": champion_id, "completed": True},
        )

    def rune_pages(self) -> ClientReply:
        return self._request("GET", "/lol-perks/v1/pages")

    def update_rune_page(self, page_id: int, payload: dict) -> ClientReply:
        return self._request("PUT", f"/lol-perks/v1/pages/{page_id}", payload)

    def create_rune_page(self, payload: dict) -> ClientReply:
        return self._request("POST", "/lol-perks/v1/pages", payload)

    def delete_rune_page(self, page_id: int) -> ClientReply:
        return self._request("DELETE", f"/lol-perks/v1/pages/{page_id}")

    def set_selection(self, selection: dict) -> ClientReply:
        return self._request("PATCH", "/lol-champ-select/v1/session/my-selection", selection)
