"""
Loads and saves the user's settings.

Sits between the UI and the config file: the UI hands over a `UserConfig` and never
learns where the file lives, what shape older versions of it had, or how a write is
made safe. Saving merges only the keys `UserConfig` owns; the repository strips
obsolete account data while preserving unrelated preferences.
"""

from __future__ import annotations

import hashlib
import json

from rune_pilot.domain.user_config import OWNED_KEYS, UserConfig
from rune_pilot.domain.champion_service import ensure_unique_role_champions
from rune_pilot.application.ports.config_store import ConfigStore


class ConfigConflict(RuntimeError):
    """Settings changed since the caller loaded them; do not overwrite them."""


class ConfigService:
    """Use cases for reading and persisting `UserConfig`."""

    def __init__(self, repository: ConfigStore) -> None:
        self.repository = repository

    def load(self) -> UserConfig:
        """
        The saved settings, migrated to the current format.

        Returns defaults on a first run or an unreadable file — never raises, so a bad
        config cannot stop the window from opening.
        """
        return UserConfig.from_raw(self.repository.read())

    @staticmethod
    def revision(config: UserConfig) -> str:
        canonical = UserConfig.from_raw(config.to_raw()).to_raw()
        encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return '"' + hashlib.sha256(encoded.encode("utf-8")).hexdigest() + '"'

    def save(self, config: UserConfig, *, expected_revision: str | None = None) -> bool:
        """
        Persists `config`, leaving every other key in the file untouched.

        Returns False if the write failed; the caller decides whether that is worth
        surfacing to the user.
        """
        ensure_unique_role_champions(config.role_champions_ui)
        owned = config.to_raw()
        conflict = False

        def mutate(data: dict) -> None:
            nonlocal conflict
            if expected_revision is not None and self.revision(UserConfig.from_raw(data)) != expected_revision:
                conflict = True
                # ConfigStore.update must abort a failed mutation without writing.
                raise ConfigConflict("Settings changed in another window")
            for key in OWNED_KEYS:
                data[key] = owned[key]

        saved = self.repository.update(mutate)
        if conflict:
            raise ConfigConflict("Settings changed in another window")
        return saved
