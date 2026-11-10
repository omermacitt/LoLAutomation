"""
HTTP client for the local RunePilot backend.

The desktop UI drives automation over HTTP instead of importing application code
directly, which keeps the two halves decoupled. This module is the only place in
`presentation/` that knows the backend's URL, timeout and wire format.

Plain `requests` functions are used rather than a `requests.Session`, because the
UI calls these methods from several short-lived worker threads and `Session` is
not thread-safe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar
from urllib.parse import quote

import requests
from pydantic import BaseModel, ValidationError

from rune_pilot.domain.game_data import ChampionCatalog, GameflowStatus, RuneCatalog, SkinOptions
from rune_pilot.domain.update import UpdateCheck, UpdateDownload, UpdateInfo
from rune_pilot.domain.user_config import UserConfig

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SEC = 3.0
QUERY_TIMEOUT_SEC = 15.0  # Catalogs can require several bounded LCU reads.
UPDATE_DOWNLOAD_TIMEOUT_SEC = 310.0
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)

_MAX_ERROR_BODY_CHARS = 300


class ApiError(RuntimeError):
    """The backend was unreachable or returned an invalid/error response."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class HealthStatus:
    """Result of a `/health` poll. `ok` is False whenever the backend did not answer."""

    ok: bool
    running: bool = False
    error: str = ""


class ApiClient:
    """Thin, synchronous wrapper over the backend's HTTP endpoints."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SEC,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._settings_revision: str | None = None
        self._uncertain_settings: UserConfig | None = None

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    @staticmethod
    def _describe(resp: requests.Response) -> str:
        body = (resp.text or "").strip()
        if len(body) > _MAX_ERROR_BODY_CHARS:
            body = body[:_MAX_ERROR_BODY_CHARS] + "…"
        return f"HTTP {resp.status_code}: {body}" if body else f"HTTP {resp.status_code}"

    def health(self) -> HealthStatus:
        """
        Polls `/health`. Never raises — an unreachable backend comes back as
        `HealthStatus(ok=False, error=...)` so callers can render it as UI state.
        """
        try:
            resp = requests.get(self._url("/health"), timeout=self.timeout)
        except Exception as e:
            return HealthStatus(ok=False, error=str(e))

        if resp.status_code != 200:
            return HealthStatus(ok=False, error=self._describe(resp))

        try:
            data = resp.json() or {}
        except ValueError as e:
            return HealthStatus(ok=False, error=f"invalid JSON in /health response: {e}")

        return HealthStatus(ok=True, running=bool(data.get("running")))

    def start_automation(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Starts the automation loop, or updates the config of a running loop."""
        return self._post("/start_automation", payload)

    def stop_automation(self) -> dict[str, Any]:
        """Stops the automation loop."""
        return self._post("/stop_automation", None)

    def load_settings(self) -> UserConfig:
        """Read validated settings; an unavailable backend never yields defaults."""
        return self._settings_request("GET")

    def check_update(self) -> UpdateInfo | None:
        return self._get_model("/updates", UpdateCheck).update

    def download_update(self, update_id: str) -> UpdateDownload:
        path = f"/updates/{quote(update_id, safe='')}/download"
        try:
            response = requests.post(
                self._url(path), timeout=max(self.timeout, UPDATE_DOWNLOAD_TIMEOUT_SEC)
            )
        except requests.RequestException as error:
            raise ApiError("Update download request failed") from error
        if response.status_code != 200:
            raise ApiError(self._describe(response), status_code=response.status_code)
        try:
            return UpdateDownload.model_validate(response.json())
        except ValueError as error:
            raise ApiError("Invalid update download response") from error

    def champion_catalog(self) -> ChampionCatalog:
        return self._get_model("/champion-catalog", ChampionCatalog)

    def gameflow(self) -> GameflowStatus:
        return self._get_model("/gameflow", GameflowStatus)

    def skin_options(self, champion_id: int) -> SkinOptions:
        return self._get_model(f"/champions/{champion_id}/skins", SkinOptions)

    def rune_catalog(self) -> RuneCatalog:
        return self._get_model("/runes/catalog", RuneCatalog)

    def perk_icon(self, perk_id: int) -> bytes | None:
        response = self._query_response(f"/runes/icons/{perk_id}")
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise ApiError(self._describe(response))
        return response.content

    def _query_response(self, path: str) -> requests.Response:
        try:
            return requests.get(self._url(path), timeout=max(self.timeout, QUERY_TIMEOUT_SEC))
        except requests.RequestException as e:
            raise ApiError(str(e)) from e

    def _get_model(self, path: str, model: type[ResponseModel]) -> ResponseModel:
        response = self._query_response(path)
        if response.status_code != 200:
            raise ApiError(self._describe(response))
        try:
            return model.model_validate(response.json())
        except (ValueError, ValidationError) as e:
            raise ApiError(f"Invalid response from {path}: {e}") from e

    def save_settings(self, config: UserConfig) -> UserConfig:
        return self._settings_request("PUT", config.to_raw())

    def _settings_request(
        self,
        method: str,
        payload: dict[str, Any] | None = None,
    ) -> UserConfig:
        if method == "PUT" and self._uncertain_settings is not None:
            try:
                current = requests.request(
                    "GET", self._url("/settings"), json=None, timeout=self.timeout
                )
                if current.status_code != 200:
                    raise ApiError(self._describe(current))
                body = current.json()
                if not isinstance(body, dict) or not UserConfig.model_fields.keys() <= body.keys():
                    raise ApiError("Invalid settings recovery response")
                config = UserConfig.model_validate(body)
                revision = getattr(current, "headers", {}).get("ETag")
                if config != self._uncertain_settings and revision != self._settings_revision:
                    raise ApiError(
                        "Settings changed in another window; local changes were retained",
                        status_code=412,
                    )
                self._settings_revision = revision if isinstance(revision, str) else None
                self._uncertain_settings = None
            except (requests.RequestException, ValueError) as error:
                raise ApiError("Could not verify the previous settings save") from error
        options: dict[str, Any] = {}
        if method == "PUT" and self._settings_revision is not None:
            options["headers"] = {"If-Match": self._settings_revision}
        try:
            resp = requests.request(
                method,
                self._url("/settings"),
                json=payload,
                timeout=self.timeout,
                **options,
            )
        except requests.RequestException as e:
            if method == "PUT":
                self._uncertain_settings = UserConfig.model_validate(payload)
            raise ApiError(str(e)) from e
        if resp.status_code != 200:
            raise ApiError(self._describe(resp))
        try:
            data = resp.json()
            if not isinstance(data, dict) or not UserConfig.model_fields.keys() <= data.keys():
                raise ValueError("incomplete settings response")
            config = UserConfig.model_validate(data)
            revision = getattr(resp, "headers", {}).get("ETag")
            self._settings_revision = revision if isinstance(revision, str) else None
            self._uncertain_settings = None
            return config
        except (ValueError, ValidationError) as e:
            if method == "PUT":
                self._uncertain_settings = UserConfig.model_validate(payload)
            raise ApiError(f"Invalid settings response: {e}") from e

    def _post(self, path: str, json_body: dict[str, Any] | None) -> dict[str, Any]:
        try:
            resp = requests.post(self._url(path), json=json_body, timeout=self.timeout)
        except Exception as e:
            raise ApiError(str(e)) from e

        if resp.status_code != 200:
            raise ApiError(self._describe(resp))

        try:
            return resp.json() or {}
        except ValueError:
            return {}
