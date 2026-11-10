"""Removing saved credentials must preserve settings in every known profile."""

import json

from fastapi.testclient import TestClient

from rune_pilot.composition.api_app import create_app
from rune_pilot.infrastructure import config_repository as module
from rune_pilot.infrastructure.config_repository import ConfigRepository


def test_purges_current_legacy_and_staged_profiles_without_changing_other_data(tmp_path):
    current, legacy = (tmp_path / name for name in ("current.json", "legacy.json"))
    expected = {
        "queue_name": "Ranked Flex",
        "custom_skins": {"TOP": {"266": 266001}},
        "extension": {"enabled": True},
    }
    paths = [current, legacy, tmp_path / "current.json.tmp", tmp_path / "legacy.json.tmp"]
    for path in paths:
        path.write_text(
            json.dumps(
                {
                    **expected,
                    "accounts": [{"username": "synthetic", "encrypted_password": "obsolete"}],
                }
            ),
            encoding="utf-8",
        )
    repository = ConfigRepository(str(current), fallback_paths=(str(legacy),))
    assert repository.remove_legacy_accounts()
    for path in paths:
        assert json.loads(path.read_text(encoding="utf-8")) == expected
    before = [path.read_bytes() for path in paths]
    assert repository.remove_legacy_accounts()
    assert [path.read_bytes() for path in paths] == before
    assert not list(tmp_path.glob(".profile-cleanup-*"))


def test_absent_profiles_are_not_created_and_corrupt_profiles_are_not_overwritten(tmp_path):
    current, legacy = tmp_path / "current.json", tmp_path / "legacy.json"
    repository = ConfigRepository(str(current), fallback_paths=(str(legacy),))
    assert repository.remove_legacy_accounts()
    assert not list(tmp_path.iterdir())
    original = '{"accounts": ["incomplete synthetic data"'
    legacy.write_text(original, encoding="utf-8")
    assert not repository.remove_legacy_accounts()
    assert legacy.read_text(encoding="utf-8") == original
    assert not current.exists()


def test_failed_cleanup_is_reported_without_rewriting_or_logging_credentials(
    tmp_path, monkeypatch, capsys
):
    profile = tmp_path / "profile.json"
    original = (
        '{"accounts":[{"encrypted_password":"synthetic-private"}],"queue_name":"Ranked Flex"}'
    )
    profile.write_text(original, encoding="utf-8")

    def denied(*_args):
        raise PermissionError("synthetic-private")

    monkeypatch.setattr(module.os, "replace", denied)
    assert not ConfigRepository(str(profile), fallback_paths=()).remove_legacy_accounts()
    assert profile.read_text(encoding="utf-8") == original
    assert not list(tmp_path.glob(".profile-cleanup-*"))
    assert "synthetic-private" not in capsys.readouterr().out


def test_startup_purges_obsolete_accounts_and_refuses_to_claim_success_on_failure(
    tmp_path, monkeypatch
):
    profile = tmp_path / "profile.json"
    profile.write_text('{"accounts":[],"queue_name":"Ranked Flex"}', encoding="utf-8")
    monkeypatch.setattr(module, "CONFIG_FILE", str(profile))
    with TestClient(create_app()) as client:
        assert client.get("/settings").json()["queue_name"] == "Ranked Flex"
    assert "accounts" not in json.loads(profile.read_text(encoding="utf-8"))
    monkeypatch.setattr(ConfigRepository, "remove_legacy_accounts", lambda _self: False)
    import pytest

    with pytest.raises(RuntimeError, match="could not be removed"):
        with TestClient(create_app()):
            pass
