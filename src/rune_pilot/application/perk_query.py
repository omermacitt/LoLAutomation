"""Perk metadata queries with instance-owned, lock-guarded caches."""

import threading
from typing import Any

from rune_pilot.application.ports.league_client import LeagueClient


class PerkQuery:
    def __init__(self, client: LeagueClient):
        self._client = client
        self._lock = threading.RLock()
        self._styles: list[dict[str, Any]] | None = None
        self._perks: list[dict[str, Any]] | None = None

    def get_perk_styles(self) -> list[dict[str, Any]]:
        with self._lock:
            if self._styles is None:
                response = self._client.perk_styles()
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, list):
                    raise ValueError("Unexpected rune styles")
                self._styles = data
            return self._styles

    def get_perks(self) -> list[dict[str, Any]]:
        with self._lock:
            if self._perks is not None:
                return self._perks
            last_error: Exception | None = None
            for game_data in (False, True):
                try:
                    response = self._client.perks(game_data=game_data)
                    response.raise_for_status()
                    data = response.json()
                    if isinstance(data, dict):
                        data = data.get("perks")
                    if isinstance(data, list):
                        self._perks = data
                        return data
                    last_error = ValueError("Unexpected perk data")
                except Exception as e:
                    last_error = e
            raise ValueError("Could not fetch perks") from last_error

    def get_perk_icon_bytes(self, asset_path: str) -> bytes | None:
        try:
            response = self._client.asset(asset_path)
            return response.content if response.status_code == 200 else None
        except Exception:
            return None
