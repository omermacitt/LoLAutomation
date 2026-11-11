"""Native-only API authority is independent of the development Vite proxy."""

from fastapi.testclient import TestClient

from rune_pilot.composition.desktop_backend import create_desktop_app

TOKEN = "synthetic-desktop-session-key-123456789"


def client_for(tmp_path):
    return TestClient(
        create_desktop_app(TOKEN, profile_dir=str(tmp_path)), base_url="http://127.0.0.1"
    )


def test_desktop_requires_parent_session_and_never_exposes_removed_routes(tmp_path):
    with client_for(tmp_path) as client:
        assert client.get("/settings").status_code == 401
        assert client.post("/start_automation", json={}).status_code == 401
        headers = {"X-RunePilot-Desktop": TOKEN}
        assert client.get("/health", headers=headers).status_code == 200
        for path in (
            "/accounts",
            "/login-jobs/active",
            "/league/launch",
            "/updates",
            "/docs",
            "/session",
        ):
            assert client.get(path, headers=headers).status_code == 404
        assert (
            client.get(
                "/health", headers={**headers, "Origin": "https://untrusted.example"}
            ).status_code
            == 403
        )
        assert (
            client.get("/health", headers={**headers, "Host": "untrusted.example"}).status_code
            == 403
        )
        assert client.get("/health?probe=1", headers=headers).status_code == 404
        assert client.get("/%68ealth", headers=headers).status_code == 404


def test_desktop_revision_and_body_guards_preserve_profile(tmp_path):
    with client_for(tmp_path) as client:
        headers = {"X-RunePilot-Desktop": TOKEN}
        loaded = client.get("/settings", headers=headers)
        config = loaded.json()
        assert client.put("/settings", json=config, headers=headers).status_code == 428
        assert (
            client.put(
                "/settings", json=config, headers={**headers, "If-Match": loaded.headers["etag"]}
            ).status_code
            == 200
        )
        assert client.post("/runes/validate", content="x", headers=headers).status_code == 415
        assert (
            client.post(
                "/runes/validate",
                content="x",
                headers={**headers, "Content-Length": str(1024 * 1024 + 1)},
            ).status_code
            == 413
        )
        assert "accounts" not in (tmp_path / "user_config.json").read_text(encoding="utf-8")
