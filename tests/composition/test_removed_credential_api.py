"""Removed credential/login surfaces cannot be reached through the backend."""

from fastapi.testclient import TestClient

from rune_pilot.application.config_service import ConfigService
from rune_pilot.composition.api_app import create_app
from rune_pilot.infrastructure.config_repository import ConfigRepository


def test_saved_account_login_and_launch_routes_are_absent(tmp_path):
    profile = tmp_path / "user_config.json"
    profile.write_text('{"queue_name":"Ranked Solo/Duo"}', encoding="utf-8")
    settings = ConfigService(ConfigRepository(str(profile), fallback_paths=()))
    app = create_app(config_service=settings)
    with TestClient(app) as client:
        for method, path in (
            ("GET", "/accounts"),
            ("POST", "/accounts"),
            ("PUT", "/accounts/removed-account"),
            ("DELETE", "/accounts/removed-account"),
            ("POST", "/accounts/removed-account/login"),
            ("GET", "/login-jobs/active"),
            ("GET", "/login-jobs/11111111-1111-4111-8111-111111111111"),
            ("POST", "/league/launch"),
        ):
            assert client.request(method, path).status_code == 404
        paths = client.get("/openapi.json").json()["paths"]
        assert not any(path.startswith(("/accounts", "/login-jobs", "/league/launch")) for path in paths)
        assert "login_running" not in client.get("/health").json()
        assert client.get("/settings").json()["queue_name"] == "Ranked Solo/Duo"
    assert not hasattr(app.state, "accounts")
    assert not hasattr(app.state, "login_jobs")
    assert not hasattr(app.state, "league_launch")
    assert profile.read_text(encoding="utf-8") == '{"queue_name":"Ranked Solo/Duo"}'
