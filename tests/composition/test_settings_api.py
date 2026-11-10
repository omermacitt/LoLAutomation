"""Settings HTTP contract and shared-file preservation."""

import json

from fastapi.testclient import TestClient

from rune_pilot.application.config_service import ConfigService
from rune_pilot.composition.api_app import create_app
from rune_pilot.domain.user_config import OWNED_KEYS, UserConfig
from rune_pilot.infrastructure.config_repository import ConfigRepository


def client_for(path):
    repository = ConfigRepository(str(path), fallback_paths=())
    return TestClient(create_app(config_service=ConfigService(repository)))


def test_missing_settings_are_complete_defaults(tmp_path):
    with client_for(tmp_path / "settings.json") as client:
        response = client.get("/settings")
    assert response.status_code == 200
    assert response.json() == UserConfig().to_raw()


def test_repeated_champions_are_rejected_without_writing_settings(tmp_path):
    path = tmp_path / "settings.json"
    original = '{"accounts": [{"id": "keep"}], "queue_name": "Ranked Flex"}'
    path.write_text(original, encoding="utf-8")
    payload = UserConfig(role_champions_ui={"TOP": [266, 266, None]}).to_raw()
    with client_for(path) as client:
        response = client.put("/settings", json=payload)
    assert response.status_code == 422
    assert path.read_text(encoding="utf-8") == original


def test_old_duplicates_leave_empty_slots_without_changing_other_roles_or_the_file(tmp_path):
    path = tmp_path / "settings.json"
    original = {
        "role_champions_ui": {"TOP": [266, "266", 103], "MIDDLE": [266, None, None]},
        "custom_summoner_spells": {"TOP": {"266": {"spell1Id": 4, "spell2Id": 14}}},
        "accounts": [{"id": "keep"}],
    }
    path.write_text(json.dumps(original), encoding="utf-8")
    with client_for(path) as client:
        response = client.get("/settings")
        assert response.status_code == 200
        payload = response.json()
        assert payload["role_champions_ui"] == {
            "TOP": [266, None, 103],
            "MIDDLE": [266, None, None],
        }
        assert payload["custom_summoner_spells"] == original["custom_summoner_spells"]
        assert json.loads(path.read_text(encoding="utf-8")) == original
        assert (
            client.put(
                "/settings", json=payload, headers={"If-Match": response.headers["etag"]}
            ).status_code
            == 200
        )
    assert "accounts" not in json.loads(path.read_text(encoding="utf-8"))


def test_settings_round_trip_removes_obsolete_accounts_and_preserves_unowned_keys(tmp_path):
    path = tmp_path / "settings.json"
    accounts = [{"id": "a1", "username": "tester", "encrypted_password": "secret"}]
    path.write_text(json.dumps({"accounts": accounts, "other": {"value": 1}}), encoding="utf-8")
    payload = UserConfig(
        queue_name="Ranked Flex", role_champions_ui={"TOP": [266, None, 1]}
    ).to_raw()
    with client_for(path) as client:
        # Obsolete account input cannot be restored through settings.
        response = client.put("/settings", json={**payload, "accounts": []})
        loaded = client.get("/settings")
    assert response.status_code == 200
    assert response.json() == loaded.json() == payload
    assert set(loaded.json()) == set(OWNED_KEYS)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert "accounts" not in saved
    assert saved["other"] == {"value": 1}


def test_get_settings_migrates_legacy_values_without_writing(tmp_path):
    path = tmp_path / "settings.json"
    raw = {"role_champions_ui": {"TOP": ["266"]}, "spell1_name": "Flash", "spell2_name": "Ignite"}
    path.write_text(json.dumps(raw), encoding="utf-8")
    with client_for(path) as client:
        response = client.get("/settings")
    assert response.json()["custom_summoner_spells"]["TOP"]["266"] == {
        "spell1Id": 4,
        "spell2Id": 14,
    }
    assert json.loads(path.read_text(encoding="utf-8")) == raw


def test_invalid_settings_do_not_touch_existing_file(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"queue_name": "Ranked Flex"}', encoding="utf-8")
    original = path.read_bytes()
    with client_for(path) as client:
        response = client.put("/settings", json={"role_champions_ui": "invalid"})
    assert response.status_code == 422
    assert path.read_bytes() == original


def test_write_failure_returns_an_error():
    class FailingStore:
        def read(self):
            return {}

        def update(self, mutate):
            return False

    with TestClient(create_app(config_service=ConfigService(FailingStore()))) as client:
        response = client.put("/settings", json=UserConfig().to_raw())
    assert response.status_code == 500
    assert response.json() == {"detail": "Could not save settings"}


def test_stale_revision_does_not_overwrite_other_window(tmp_path):
    path = tmp_path / "settings.json"
    with client_for(path) as client:
        first = client.get("/settings")
        revision = first.headers["etag"]
        accepted = client.put(
            "/settings",
            json=UserConfig(queue_name="Ranked Flex").to_raw(),
            headers={"If-Match": revision},
        )
        assert accepted.status_code == 200
        assert accepted.headers["etag"] != revision
        before = path.read_bytes()
        rejected = client.put("/settings", json=first.json(), headers={"If-Match": revision})
        assert rejected.status_code == 412
        assert path.read_bytes() == before
        assert client.get("/settings").headers["etag"] == accepted.headers["etag"]


def test_foreign_preference_changes_do_not_conflict_with_settings_save(tmp_path):
    path = tmp_path / "settings.json"
    with client_for(path) as client:
        initial = client.get("/settings")
        preferences = {"theme": "dark"}
        ConfigRepository(str(path), fallback_paths=()).update(
            lambda data: data.update({"preferences": preferences})
        )
        response = client.put(
            "/settings",
            json=UserConfig(queue_name="Normal Draft").to_raw(),
            headers={"If-Match": initial.headers["etag"]},
        )
        assert response.status_code == 200
        assert client.get("/settings").headers["etag"] == response.headers["etag"]
    assert json.loads(path.read_text(encoding="utf-8"))["preferences"] == preferences
