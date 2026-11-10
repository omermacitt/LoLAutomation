"""Read-only editor queries and catalog-backed validation; no game writes."""

from collections.abc import Callable

from rune_pilot.application.game_query_service import GameQueryService, QueryUnavailable
from rune_pilot.domain.rune_editor import (
    RuneEditorCatalog,
    RunePage,
    RuneRecommendation,
    normalize_editor_catalog,
    validate_editor_page,
)


class RuneEditorService:
    def __init__(self, queries: GameQueryService, recommended: Callable[[int], dict | None]):
        self._queries = queries
        self._recommended = recommended

    def catalog(self) -> RuneEditorCatalog:
        raw = self._queries.rune_catalog()
        try:
            return normalize_editor_catalog(raw.styles, raw.perks)
        except ValueError as error:
            raise QueryUnavailable("Could not load complete rune editor data") from error

    def validate(self, page: RunePage) -> RunePage:
        return validate_editor_page(page, self.catalog())

    def recommendation(self, champion_id: int) -> RuneRecommendation:
        page = self._recommended(champion_id)
        if page is None:
            return RuneRecommendation(champion_id=champion_id, unavailableReason="missing")
        catalog = self.catalog()
        try:
            normalized = validate_editor_page(
                RunePage.model_validate({**page, "name": "Önerilen"}), catalog
            )
            return RuneRecommendation(champion_id=champion_id, page=normalized)
        except ValueError:
            return RuneRecommendation(champion_id=champion_id, unavailableReason="outdated")
