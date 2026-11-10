"""Load recommendation data and champion identity, then apply pure rune rules."""

from rune_pilot.application.ports.rune_data import RuneDataSource
from rune_pilot.application.champion_query import ChampionQuery
from rune_pilot.domain.rune_rules import recommended_page


class RuneService:
    def __init__(self, source: RuneDataSource, champions: ChampionQuery):
        self._source = source
        self._champions = champions

    def get_recommended_page_for_champion(self, champ_id: int) -> dict | None:
        data = self._source.get_runes_data()
        direct = data.get(str(champ_id))
        direct_format = isinstance(direct, dict) and all(
            key in direct for key in ("primaryStyleId", "subStyleId", "selectedPerkIds")
        )
        slug = None if direct_format else self._champions.get_champion_slug_by_id(champ_id)
        return recommended_page(champ_id, data, slug)
