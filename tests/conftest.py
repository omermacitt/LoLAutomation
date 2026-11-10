"""
Shared pytest fixtures.

Tests use temporary storage and injected/stubbed collaborators without a running
League Client. Headless Qt fixtures live in presentation/conftest.py so backend
and architecture checks can also run independently of the UI.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_default_profile(tmp_path, monkeypatch):
    """Production-style app startup must never migrate the real user profile."""
    from rune_pilot.infrastructure import config_repository

    monkeypatch.setattr(
        config_repository, "CONFIG_FILE", str(tmp_path / "current" / "user_config.json")
    )
    monkeypatch.setattr(
        config_repository, "LEGACY_APP_CONFIG_FILE", str(tmp_path / "legacy" / "user_config.json")
    )
    monkeypatch.setattr(config_repository, "LEGACY_CONFIG_FILE", "")


@pytest.fixture()
def config_path(tmp_path):
    """Path to a config file inside a per-test temporary directory."""
    return str(tmp_path / "user_config.json")
