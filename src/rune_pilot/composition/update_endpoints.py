"""Desktop update discovery and installer download routes."""

from fastapi import Depends, FastAPI, HTTPException, Request

from rune_pilot.application.update_service import UpdateService, UnknownUpdate, UpdateDownloadFailed
from rune_pilot.domain.update import UpdateCheck, UpdateDownload


def get_updates(request: Request) -> UpdateService:
    return request.app.state.updates


def register_update_routes(app: FastAPI) -> None:
    @app.get("/updates", response_model=UpdateCheck)
    def check(service: UpdateService = Depends(get_updates)):
        return UpdateCheck(update=service.check())

    @app.post("/updates/{update_id}/download", response_model=UpdateDownload)
    def download(update_id: str, service: UpdateService = Depends(get_updates)):
        try:
            return service.download(update_id)
        except UnknownUpdate as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except UpdateDownloadFailed as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
