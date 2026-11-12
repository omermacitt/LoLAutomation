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
    def __init__(self, queries: GameQueryService, recommended: Callable[[int, str], list[dict]]):
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

    def recommendation(self, champion_id: int, role: str | None = None) -> RuneRecommendation:
        if role is None:
            return RuneRecommendation(champion_id=champion_id, unavailableReason="role_required")
        pages = self._recommended(champion_id, role)
        if not pages:
            return RuneRecommendation(
                champion_id=champion_id, role=role, unavailableReason="missing"
            )
        catalog = self.catalog()
        options = []
        for page in pages:
            try:
                normalized = validate_editor_page(RunePage.model_validate(page), catalog)
                if normalized not in options:
                    options.append(normalized)
            except ValueError:
                continue
        return RuneRecommendation(
            champion_id=champion_id,
            role=role,
            page=options[0] if options else None,
            options=options,
            unavailableReason=None if options else "outdated",
        )
