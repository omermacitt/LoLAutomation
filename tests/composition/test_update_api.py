"""Update routes use registered releases, hide tokens and never accept paths/URLs."""

from unittest.mock import Mock

from fastapi.testclient import TestClient

from rune_pilot.application.update_service import UpdateService
from rune_pilot.composition.api_app import create_app


def release():
    return {"tag_name": "v2.0", "body": "Changes", "html_url": "https://github.com/test/app/releases/tag/v2.0",
            "assets": [{"name": "Setup.exe", "browser_download_url": "https://github.com/test/app/releases/download/v2.0/Setup.exe"}]}


def test_update_check_registered_download_and_retry_use_one_backend_download():
    source = Mock()
    source.latest_release.return_value = release()
    source.download.return_value = "C:/temp/runepilot-update-123/Setup.exe"
    service = UpdateService(source, current_version="1.0")
    with TestClient(create_app(update_service=service)) as client:
        info = client.get("/updates").json()["update"]
        assert info["current_version"] == "1.0"
        assert info["latest_version"] == "2.0"
        assert client.get("/updates").json()["update"]["update_id"] == info["update_id"]
        path = f"/updates/{info['update_id']}/download"
        response = client.post(path, json={"url": "http://arbitrary.test/", "dest_path": "C:/private.exe"})
        assert response.status_code == 200
        assert response.json() == {"installer_path": source.download.return_value}
        assert client.post(path).json() == response.json()
        assert client.post("/updates/unknown/download").status_code == 404
    source.download.assert_called_once()
    downloaded_info = source.download.call_args.args[0]
    assert downloaded_info.asset_download_url == release()["assets"][0]["browser_download_url"]


def test_update_check_silently_handles_offline_disabled_and_current_version():
    source = Mock()
    source.latest_release.side_effect = OSError("private token")
    with TestClient(create_app(update_service=UpdateService(source, current_version="1.0"))) as client:
        assert client.get("/updates").json() == {"update": None}
    source.latest_release.reset_mock()
    with TestClient(create_app(update_service=UpdateService(source, current_version="1.0", enabled=False))) as client:
        assert client.get("/updates").json() == {"update": None}
    source.latest_release.assert_not_called()
    source.latest_release.side_effect = None
    source.latest_release.return_value = release()
    assert UpdateService(source, current_version="v2.0").check() is None


def test_failed_download_is_sanitized_and_can_be_retried():
    source = Mock()
    source.latest_release.return_value = release()
    source.download.side_effect = OSError("Authorization: private token; C:/private/path")
    with TestClient(create_app(update_service=UpdateService(source, current_version="1.0"))) as client:
        info = client.get("/updates").json()["update"]
        path = f"/updates/{info['update_id']}/download"
        response = client.post(path)
        assert response.status_code == 502
        assert "private" not in response.text
        source.download.side_effect = None
        source.download.return_value = "C:/temp/Setup.exe"
        assert client.post(path).status_code == 200


def test_offer_history_is_bounded_and_release_without_installer_cannot_download():
    source = Mock()
    source.latest_release.return_value = {"tag_name": "2", "assets": []}
    service = UpdateService(source, current_version="1")
    with TestClient(create_app(update_service=service)) as client:
        first = client.get("/updates").json()["update"]
        assert first["asset_download_url"] == ""
        assert client.post(f"/updates/{first['update_id']}/download").status_code == 404
        for version in range(3, 14):
            source.latest_release.return_value = {**release(), "tag_name": str(version)}
            client.get("/updates")
        assert len(service._offers) == 8
        assert client.post(f"/updates/{first['update_id']}/download").status_code == 404
    source.download.assert_not_called()


def test_update_environment_is_wired_only_in_backend(monkeypatch):
    monkeypatch.setenv("RUNEPILOT_DISABLE_AUTO_UPDATE", "true")
    monkeypatch.setenv("RUNEPILOT_UPDATE_REPO", "custom/repo")
    monkeypatch.setenv("RUNEPILOT_GITHUB_TOKEN", "private-value")
    app = create_app()
    source = app.state.updates._source
    assert source._repo == "custom/repo"
    assert source._token == "private-value"
    with TestClient(app) as client:
        response = client.get("/updates")
        assert response.json() == {"update": None}
        assert "private-value" not in response.text
