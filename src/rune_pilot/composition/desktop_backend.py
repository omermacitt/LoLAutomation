"""Authenticated loopback boundary for the packaged, parent-owned backend."""

import hmac
import json
import re
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from rune_pilot.application.config_service import ConfigService
from rune_pilot.composition.api_app import create_app
from rune_pilot.infrastructure.config_repository import ConfigRepository

PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 1024 * 1024
ROUTES = json.loads(Path(__file__).with_name("desktop_routes.json").read_text(encoding="utf-8"))


def allowed_request(method: str, path: str, *, image_only: bool = False) -> bool:
    return any(
        item["method"] == method
        and (not image_only or item["image"])
        and re.fullmatch(item["pattern"], path) is not None
        for item in ROUTES
    )


def create_desktop_app(
    token: str,
    *,
    profile_dir: str | None = None,
    factory: Callable[..., FastAPI] = create_app,
) -> FastAPI:
    if len(token) < 32 or not token.isascii():
        raise ValueError("Invalid desktop session")
    service = None
    if profile_dir is not None:
        repository = ConfigRepository(
            str(Path(profile_dir) / "user_config.json"), fallback_paths=()
        )
        if not repository.remove_legacy_accounts():
            raise RuntimeError("Could not migrate the desktop profile")
        service = ConfigService(repository)
    app = factory(config_service=service)
    app.state.desktop_protocol = PROTOCOL_VERSION

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        supplied = request.headers.get("x-runepilot-desktop", "")
        if not supplied.isascii() or not hmac.compare_digest(supplied, token):
            return JSONResponse({"detail": "Desktop session required"}, status_code=401)
        # Requests originate from the native host, never a web page.
        if request.headers.get("origin") or request.url.hostname != "127.0.0.1":
            return JSONResponse({"detail": "Invalid desktop origin"}, status_code=403)
        path = request.url.path
        if request.scope.get("query_string") or request.scope.get("raw_path", b"") != path.encode():
            return JSONResponse({"detail": "Invalid desktop route"}, status_code=404)
        if not allowed_request(request.method, path):
            return JSONResponse({"detail": "Desktop route unavailable"}, status_code=404)
        if request.method != "GET":
            try:
                length = int(request.headers.get("content-length", "0"))
            except ValueError:
                return JSONResponse({"detail": "Invalid request length"}, status_code=400)
            if length < 0 or length > MAX_REQUEST_BYTES:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
            body = await request.body()
            if len(body) > MAX_REQUEST_BYTES:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
            if path != "/stop_automation" and not request.headers.get(
                "content-type", ""
            ).startswith("application/json"):
                return JSONResponse({"detail": "JSON request required"}, status_code=415)
            if path == "/settings" and not request.headers.get("if-match"):
                return JSONResponse({"detail": "Settings revision required"}, status_code=428)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return app
