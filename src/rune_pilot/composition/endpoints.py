"""RunePilot HTTP routes for health, automation, champions and settings."""

from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Request, Response

from rune_pilot.application.automation_service import AutomationService
from rune_pilot.application.champion_query import ChampionQuery
from rune_pilot.application.champion_portrait_query import ChampionPortraitQuery
from rune_pilot.application.skin_artwork_query import SkinArtworkQuery
from rune_pilot.application.rune_editor_service import RuneEditorService
from rune_pilot.application.config_service import ConfigConflict, ConfigService
from rune_pilot.application.game_query_service import GameQueryService, QueryUnavailable
from rune_pilot.domain.game_data import ChampionCatalog, GameflowStatus, RuneCatalog, SkinOptions
from rune_pilot.domain.rune_editor import RuneEditorCatalog, RunePage, RuneRecommendation
from rune_pilot.domain.models import AutomationConfig
from rune_pilot.domain.champion_service import DuplicateChampionChoices
from rune_pilot.domain.user_config import UserConfig
from rune_pilot.shared.app_meta import __version__


def get_automation_service(request: Request) -> AutomationService:
    """The single `AutomationService` built in `create_app()`."""
    return request.app.state.automation


def get_config_service(request: Request) -> ConfigService:
    """Settings service wired by the application factory."""
    return request.app.state.settings


def get_game_queries(request: Request) -> GameQueryService:
    return request.app.state.game_queries


def get_champion_query(request: Request) -> ChampionQuery:
    return request.app.state.champions


def get_champion_portraits(request: Request) -> ChampionPortraitQuery:
    return request.app.state.champion_portraits


def get_rune_editor(request: Request) -> RuneEditorService:
    return request.app.state.rune_editor


def get_skin_artwork(request: Request) -> SkinArtworkQuery:
    return request.app.state.skin_artwork


def register_routes(app: FastAPI) -> None:
    """Registers all FastAPI routes on the app."""

    @app.exception_handler(QueryUnavailable)
    async def query_unavailable(_request: Request, error: QueryUnavailable):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"detail": str(error)})

    @app.get("/champion-catalog", response_model=ChampionCatalog)
    def champion_catalog(service: GameQueryService = Depends(get_game_queries)):
        return service.champion_catalog()

    @app.get("/gameflow", response_model=GameflowStatus)
    def gameflow(service: GameQueryService = Depends(get_game_queries)):
        return service.gameflow()

    @app.get("/champions/{champion_id}/portrait")
    def champion_portrait(champion_id: int = Path(gt=0), service: ChampionPortraitQuery = Depends(get_champion_portraits)):
        data = service.portrait(champion_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Champion portrait unavailable", headers={"Cache-Control": "no-store"})
        return Response(content=data, media_type="image/png", headers={
            "Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff",
        })

    @app.get("/champions/{champion_id}/skins", response_model=SkinOptions)
    def skins(champion_id: int = Path(gt=0), service: GameQueryService = Depends(get_game_queries)):
        return service.skins(champion_id)

    @app.get("/champions/{champion_id}/skins/{skin_id}/artwork")
    def skin_artwork(champion_id: int = Path(gt=0), skin_id: int = Path(gt=0), service: SkinArtworkQuery = Depends(get_skin_artwork)):
        artwork = service.artwork(champion_id, skin_id)
        if artwork is None:
            raise HTTPException(status_code=404, detail="Skin artwork unavailable", headers={"Cache-Control": "no-store"})
        data, media_type = artwork
        return Response(content=data, media_type=media_type, headers={
            "Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff",
        })

    @app.get("/runes/catalog", response_model=RuneCatalog)
    def rune_catalog(service: GameQueryService = Depends(get_game_queries)):
        return service.rune_catalog()

    @app.get("/runes/editor-catalog", response_model=RuneEditorCatalog)
    def rune_editor_catalog(service: RuneEditorService = Depends(get_rune_editor)):
        return service.catalog()

    @app.get("/champions/{champion_id}/runes/recommended", response_model=RuneRecommendation)
    def recommended_runes(champion_id: int = Path(gt=0), service: RuneEditorService = Depends(get_rune_editor)):
        return service.recommendation(champion_id)

    @app.post("/runes/validate", response_model=RunePage)
    def validate_runes(page: RunePage, service: RuneEditorService = Depends(get_rune_editor)):
        try:
            return service.validate(page)
        except ValueError as error:
            raise HTTPException(status_code=422, detail="Rune page is incompatible with the current catalog") from error

    @app.get("/runes/icons/{perk_id}")
    def rune_icon(perk_id: int = Path(gt=0), service: GameQueryService = Depends(get_game_queries)):
        data = service.icon(perk_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Rune icon unavailable")
        return Response(content=data, media_type="image/png", headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"})

    @app.get("/health")
    def health(service: AutomationService = Depends(get_automation_service)):
        """Simple health-check endpoint."""
        running = service.is_running
        return {"status": "ok", "running": running, "version": __version__,
                "selection": app.state.selection_feedback.read() if running else None}

    @app.get("/champions")
    def champions(service: ChampionQuery = Depends(get_champion_query)):
        """Returns the list of owned champions for the UI."""
        return service.get_champions()

    @app.get("/settings", response_model=UserConfig)
    def settings(response: Response, service: ConfigService = Depends(get_config_service)) -> UserConfig:
        config = service.load()
        response.headers["ETag"] = service.revision(config)
        response.headers["Cache-Control"] = "no-store"
        return config

    @app.put("/settings", response_model=UserConfig)
    def save_settings(
        config: UserConfig,
        response: Response,
        if_match: str | None = Header(default=None, alias="If-Match"),
        service: ConfigService = Depends(get_config_service),
    ) -> UserConfig:
        try:
            saved = service.save(config, expected_revision=if_match)
        except ConfigConflict as error:
            raise HTTPException(status_code=412, detail="Settings changed in another window") from error
        except DuplicateChampionChoices as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if not saved:
            raise HTTPException(status_code=500, detail="Could not save settings")
        response.headers["ETag"] = service.revision(config)
        response.headers["Cache-Control"] = "no-store"
        return config

    @app.post("/start_automation")
    def start_automation(
        config: AutomationConfig,
        service: AutomationService = Depends(get_automation_service),
    ):
        """Starts the automation loop, or swaps in a new config if it is already running."""
        status = service.start(config.model_dump())
        return {"status": status, "config": service.config}

    @app.put("/automation/config")
    def update_running_config(
        config: AutomationConfig,
        service: AutomationService = Depends(get_automation_service),
    ):
        if not service.update_running(config.model_dump()):
            raise HTTPException(status_code=409, detail="Automation is not running")
        return {"status": "updated", "config": service.config}

    @app.post("/stop_automation")
    def stop_automation(service: AutomationService = Depends(get_automation_service)):
        """Stops the automation loop (the thread exits on its next iteration)."""
        service.stop()
        return {"status": "stopped"}
