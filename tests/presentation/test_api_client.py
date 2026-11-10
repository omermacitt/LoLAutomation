"""HTTP errors must never be interpreted as successfully loaded defaults."""

from unittest.mock import Mock

import pytest
import requests

from rune_pilot.domain.user_config import UserConfig
from rune_pilot.presentation.api_client import ApiClient, ApiError
from rune_pilot.domain.game_data import ChampionCatalog, GameflowStatus, RuneCatalog, SkinOptions
from rune_pilot.domain.update import UpdateInfo, UpdateDownload


def test_update_client_validates_contract_and_uses_backend_download_with_long_timeout(monkeypatch):
    response = Mock(status_code=200)
    info = UpdateInfo(update_id="known-id", latest_version="2")
    response.json.return_value = {"update": info.model_dump()}
    get = Mock(return_value=response)
    post = Mock(return_value=response)
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(requests, "post", post)
    client = ApiClient("http://backend.test")
    assert client.check_update() == info
    assert get.call_args.args == ("http://backend.test/updates",)
    response.json.return_value = {"installer_path": "C:/temp/Setup.exe"}
    assert client.download_update("known-id") == UpdateDownload(installer_path="C:/temp/Setup.exe")
    post.assert_called_once_with("http://backend.test/updates/known-id/download", timeout=310.0)
    response.json.return_value = {"installer_path": ""}
    with pytest.raises(ApiError, match="Invalid update"):
        client.download_update("known-id")
    response.status_code = 502
    response.text = "Download failed"
    with pytest.raises(ApiError, match="HTTP 502"):
        client.download_update("known-id")


def test_settings_client_uses_validated_wire_contract(monkeypatch):
    config = UserConfig(queue_name="Ranked Flex")
    response = Mock(status_code=200)
    response.json.return_value = config.to_raw()
    request = Mock(return_value=response)
    monkeypatch.setattr(requests, "request", request)
    client = ApiClient(base_url="http://example.test/", timeout=1)
    assert client.load_settings() == config
    request.assert_called_with("GET", "http://example.test/settings", json=None, timeout=1)
    assert client.save_settings(config) == config
    request.assert_called_with("PUT", "http://example.test/settings", json=config.to_raw(), timeout=1)


def test_settings_client_preserves_revision_for_conditional_writes(monkeypatch):
    response = Mock(status_code=200, headers={"ETag": '"first"'})
    response.json.return_value = UserConfig().to_raw()
    request = Mock(return_value=response)
    monkeypatch.setattr(requests, "request", request)
    client = ApiClient()
    config = client.load_settings()
    response.headers = {"ETag": '"second"'}
    client.save_settings(config)
    assert request.call_args.kwargs["headers"] == {"If-Match": '"first"'}
    client.save_settings(config)
    assert request.call_args.kwargs["headers"] == {"If-Match": '"second"'}


def test_settings_client_recovers_a_lost_successful_write_without_overwriting_other_changes(monkeypatch):
    original = UserConfig()
    saved = UserConfig(queue_name="Normal Draft")
    latest = UserConfig(queue_name="Ranked Flex")

    def response(config, revision):
        result = Mock(status_code=200, headers={"ETag": revision})
        result.json.return_value = config.to_raw()
        return result

    request = Mock(side_effect=[response(original, '"a"'), requests.ReadTimeout(), response(saved, '"b"'), response(latest, '"c"')])
    monkeypatch.setattr(requests, "request", request)
    client = ApiClient()
    client.load_settings()
    with pytest.raises(ApiError):
        client.save_settings(saved)
    assert client.save_settings(latest) == latest
    assert request.call_args.kwargs["headers"] == {"If-Match": '"b"'}


@pytest.mark.parametrize("body", [None, [], {}, {"status": "ok"}, {**UserConfig().to_raw(), "role_champions_ui": "bad"}])
def test_malformed_response_is_not_defaults(monkeypatch, body):
    response = Mock(status_code=200)
    response.json.return_value = body
    monkeypatch.setattr(requests, "request", Mock(return_value=response))
    with pytest.raises(ApiError, match="Invalid settings response"):
        ApiClient().load_settings()


def test_invalid_json_is_reported(monkeypatch):
    response = Mock(status_code=200)
    response.json.side_effect = ValueError("invalid JSON")
    monkeypatch.setattr(requests, "request", Mock(return_value=response))
    with pytest.raises(ApiError, match="invalid JSON"):
        ApiClient().load_settings()


def test_network_error_and_save_error_are_reported(monkeypatch):
    request = Mock(side_effect=requests.ConnectionError("offline"))
    monkeypatch.setattr(requests, "request", request)
    with pytest.raises(ApiError, match="offline"):
        ApiClient().load_settings()
    request.side_effect = None
    request.return_value = Mock(status_code=500, text="Could not save settings")
    with pytest.raises(ApiError, match="HTTP 500"):
        ApiClient().save_settings(UserConfig())


@pytest.mark.parametrize("method,args,path,model,body", [
    ("champion_catalog", (), "/champion-catalog", ChampionCatalog,
     {"all_champions": [{"id": 266, "name": "Aatrox"}], "pickable_champions": []}),
    ("gameflow", (), "/gameflow", GameflowStatus, {"phase": None}),
    ("skin_options", (266,), "/champions/266/skins", SkinOptions,
     {"champion_id": 266, "skins": [{"id": 266000, "name": "Default"}]}),
    ("rune_catalog", (), "/runes/catalog", RuneCatalog,
     {"styles": [{"id": 8000}], "perks": [{"id": 8005}]}),
])
def test_game_queries_use_typed_contracts(monkeypatch, method, args, path, model, body):
    response = Mock(status_code=200)
    response.json.return_value = body
    get = Mock(return_value=response)
    monkeypatch.setattr(requests, "get", get)
    result = getattr(ApiClient(base_url="http://example.test"), method)(*args)
    assert isinstance(result, model)
    assert result.model_dump() == body
    assert get.call_args.args == ("http://example.test" + path,)
    assert get.call_args.kwargs["timeout"] > 3


@pytest.mark.parametrize("method,args", [("champion_catalog", ()), ("gameflow", ()), ("skin_options", (266,)), ("rune_catalog", ())])
def test_incomplete_game_responses_are_errors(monkeypatch, method, args):
    response = Mock(status_code=200)
    response.json.return_value = {}
    monkeypatch.setattr(requests, "get", Mock(return_value=response))
    with pytest.raises(ApiError, match="Invalid response"):
        getattr(ApiClient(), method)(*args)


def test_unavailable_query_and_optional_icon_errors(monkeypatch):
    get = Mock(return_value=Mock(status_code=503, text="LCU unavailable"))
    monkeypatch.setattr(requests, "get", get)
    with pytest.raises(ApiError, match="HTTP 503"):
        ApiClient().champion_catalog()
    get.return_value = Mock(status_code=404)
    assert ApiClient().perk_icon(8005) is None
    get.return_value = Mock(status_code=200, content=b"png")
    assert ApiClient().perk_icon(8005) == b"png"
    get.side_effect = requests.Timeout("query timeout")
    with pytest.raises(ApiError, match="query timeout"):
        ApiClient().gameflow()
