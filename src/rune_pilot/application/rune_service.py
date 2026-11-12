"""Read champion/role recommendations from League, without files or web sources."""

from rune_pilot.application.game_query_service import QueryUnavailable
from rune_pilot.application.ports.league_client import LeagueClient
from rune_pilot.domain.constants import ROLE_KEYS
from rune_pilot.domain.league_runes import recommendation_pages


class RuneService:
    def __init__(self, client: LeagueClient):
        self._client = client

    def get_recommended_pages(self, champion_id: int, role: str, map_id: int = 11) -> list[dict]:
        if role not in ROLE_KEYS or map_id != 11 or champion_id <= 0:
            return []
        try:
            reply = self._client.recommended_runes(champion_id, role, map_id)
            if reply.status_code != 200:
                raise ValueError("Unavailable recommendation response")
            raw = reply.json()
            if not isinstance(raw, list):
                raise ValueError("Invalid recommendation response")
            return recommendation_pages(raw, champion_id, role)
        except Exception as error:
            raise QueryUnavailable(
                "League rune recommendations are unavailable. Retry with the League Client open."
            ) from error
