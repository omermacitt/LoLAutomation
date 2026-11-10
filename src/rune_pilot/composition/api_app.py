"""RunePilot FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI

from rune_pilot.application.automation import AutomationRunner
from rune_pilot.application.automation_service import AutomationService
from rune_pilot.application.champion_portrait_query import ChampionPortraitQuery
from rune_pilot.application.champion_query import ChampionQuery
from rune_pilot.application.config_service import ConfigService
from rune_pilot.application.game_query_service import GameQueryService
from rune_pilot.application.lobby_service import LobbyService
from rune_pilot.application.perk_query import PerkQuery
from rune_pilot.application.ports.league_client import LeagueClient
from rune_pilot.application.ports.rune_data import RuneDataSource
from rune_pilot.application.rune_editor_service import RuneEditorService
from rune_pilot.application.rune_service import RuneService
from rune_pilot.application.skin_artwork_query import SkinArtworkQuery
from rune_pilot.application.skin_query import SkinQuery
from rune_pilot.application.update_service import UpdateService
from rune_pilot.composition.endpoints import register_routes
from rune_pilot.composition.update_endpoints import register_update_routes
from rune_pilot.infrastructure.config_repository import ConfigRepository
from rune_pilot.infrastructure.github_updates import GithubUpdateSource
from rune_pilot.infrastructure.league_client_adapter import LcuLeagueClient
from rune_pilot.infrastructure.rune_data_provider import JsonRuneData
from rune_pilot.shared.app_meta import UPDATE_REPO_DEFAULT, __version__


def create_app(
    automation_service: AutomationService | None = None,
    config_service: ConfigService | None = None,
    game_queries: GameQueryService | None = None,
    league_client: LeagueClient | None = None,
    rune_source: RuneDataSource | None = None,
    update_service: UpdateService | None = None,
) -> FastAPI:
    """
    Creates and configures the FastAPI application.

    Shared backend services live on `app.state`. Composition injects storage and
    external adapters; tests can supply temporary storage and synthetic League
    operations without a running client.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            if config_service is None and not await asyncio.to_thread(
                repository.remove_legacy_accounts
            ):
                raise RuntimeError(
                    "Saved account data could not be removed. Close older RunePilot instances and check profile permissions."
                )
            yield
        finally:
            if not await asyncio.to_thread(app.state.automation.shutdown):
                logging.getLogger(__name__).warning(
                    "Automation worker did not finish within the shutdown timeout"
                )

    application = FastAPI(title="RunePilot API", lifespan=lifespan)
    client = league_client if league_client is not None else LcuLeagueClient()
    source = rune_source if rune_source is not None else JsonRuneData()
    champions = ChampionQuery(client)
    perks = PerkQuery(client)
    skins = SkinQuery(client)
    lobby = LobbyService(client, champions)
    runes = RuneService(source, champions)
    runner = AutomationRunner(client, champions, runes, lobby)
    application.state.selection_feedback = runner.feedback
    application.state.champions = champions
    application.state.champion_portraits = ChampionPortraitQuery(client)
    application.state.skin_artwork = SkinArtworkQuery(client)
    application.state.updates = (
        update_service
        if update_service is not None
        else UpdateService(
            GithubUpdateSource(
                (os.getenv("RUNEPILOT_UPDATE_REPO") or UPDATE_REPO_DEFAULT or "").strip(),
                (os.getenv("RUNEPILOT_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN") or "").strip()
                or None,
            ),
            current_version=__version__,
            enabled=(os.getenv("RUNEPILOT_DISABLE_AUTO_UPDATE") or "").strip().lower()
            not in {"1", "true", "yes", "on"},
        )
    )
    repository = config_service.repository if config_service is not None else ConfigRepository()
    application.state.automation = (
        automation_service if automation_service is not None else AutomationService(runner.run)
    )
    application.state.settings = (
        config_service if config_service is not None else ConfigService(repository)
    )
    application.state.game_queries = (
        game_queries
        if game_queries is not None
        else GameQueryService(
            champion_summary=partial(champions.get_champion_summary, strict=True),
            owned_champions=partial(champions.get_owned_champions_raw, strict=True),
            gameflow_phase=lobby.get_gameflow_phase_safe,
            skin_options=partial(skins.get_skin_options_for_champion, strict=True),
            perk_styles=perks.get_perk_styles,
            perks=perks.get_perks,
            perk_icon=perks.get_perk_icon_bytes,
        )
    )
    application.state.rune_editor = RuneEditorService(
        application.state.game_queries, runes.get_recommended_page_for_champion
    )
    register_routes(application)
    register_update_routes(application)
    return application


app = create_app()
