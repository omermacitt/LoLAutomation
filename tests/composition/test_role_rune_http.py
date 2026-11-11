from fastapi.testclient import TestClient

from rune_pilot.application.config_service import ConfigService
from rune_pilot.composition.api_app import create_app
from rune_pilot.infrastructure.config_repository import ConfigRepository


def test_http_role_assignments_normalize_round_trip_and_participate_in_etag(tmp_path):
    service = ConfigService(ConfigRepository(str(tmp_path / "settings.json"), fallback_paths=()))
    app = create_app(config_service=service)
    with TestClient(app) as client:
        loaded = client.get("/settings")
        config = loaded.json()
        config["role_rune_selection"] = {"TOP": {"106": False}, "MIDDLE": {"106": 2}}
        saved = client.put("/settings", json=config, headers={"If-Match": loaded.headers["etag"]})
        assert saved.status_code == 200
        assert saved.json()["role_rune_selection"] == {"TOP": {"106": 0}, "MIDDLE": {"106": 2}}
        assert saved.headers["etag"] != loaded.headers["etag"]
        assert client.get("/settings").json() == saved.json()
        conflict = client.put(
            "/settings", json=loaded.json(), headers={"If-Match": loaded.headers["etag"]}
        )
        assert conflict.status_code == 412
        assert client.get("/settings").json() == saved.json()
        assert not app.state.automation.is_running
