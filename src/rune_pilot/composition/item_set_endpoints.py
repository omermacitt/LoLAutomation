"""Narrow item-set and static game-data HTTP routes."""

from fastapi import FastAPI, Header, HTTPException, Path, Response
from pydantic import BaseModel, Field

from rune_pilot.application.item_set_service import ItemSetConflict, ItemSetService, revision
from rune_pilot.domain.item_sets import ChampionItemStats, ItemCatalog, ItemSetCollection


class ClientItemState(BaseModel):
    revision: str = Field(min_length=20, max_length=100)
    set_count: int = Field(ge=0)


class ExportItemSet(BaseModel):
    client_revision: str = Field(min_length=20, max_length=100)


def register_item_set_routes(app: FastAPI):
    def service() -> ItemSetService:
        return app.state.item_sets

    @app.exception_handler(ItemSetConflict)
    async def item_set_conflict(_request, _error):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=412, content={"detail": "Item sets changed; reload before saving"}
        )

    @app.get("/item-builder/catalog", response_model=ItemCatalog)
    def catalog():
        return service().catalog()

    @app.get("/item-builder/champions/{champion_id}", response_model=ChampionItemStats)
    def champion(champion_id: int = Path(gt=0)):
        try:
            return service().champion(champion_id)
        except ValueError as error:
            raise HTTPException(404, "Unknown champion") from error

    @app.get("/item-builder/items/{item_id}/icon")
    def icon(item_id: int = Path(gt=0)):
        try:
            data = service().icon(item_id)
        except ValueError as error:
            raise HTTPException(404, "Unknown item") from error
        return Response(
            data,
            media_type="image/png",
            headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"},
        )

    @app.get("/item-sets", response_model=ItemSetCollection)
    def item_sets(response: Response):
        data = service().load()
        response.headers["ETag"] = revision(data.model_dump())
        response.headers["Cache-Control"] = "no-store"
        return data

    @app.put("/item-sets", response_model=ItemSetCollection)
    def save(
        data: ItemSetCollection, response: Response, if_match: str | None = Header(default=None)
    ):
        if if_match is None:
            raise HTTPException(428, "Item sets revision required")
        try:
            saved = service().save(data, if_match)
        except ValueError as error:
            raise HTTPException(422, "Invalid item-set contents") from error
        response.headers["ETag"] = revision(saved.model_dump())
        return saved

    @app.get("/item-sets/client-state", response_model=ClientItemState)
    def client_state():
        return service().client_state()

    @app.post("/item-sets/{uid}/export", response_model=ClientItemState)
    def export(uid: str, data: ExportItemSet, if_match: str | None = Header(default=None)):
        if if_match is None:
            raise HTTPException(428, "Local item-set revision required")
        try:
            return service().export(uid, data.client_revision, if_match)
        except ValueError as error:
            raise HTTPException(422, "Save a valid item set before exporting") from error
