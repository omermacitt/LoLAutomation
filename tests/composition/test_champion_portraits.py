"""Portrait reads are known-ID only, bounded, cached and retryable."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from rune_pilot.application.champion_portrait_query import ChampionPortraitQuery, PNG_SIGNATURE
from rune_pilot.composition.api_app import create_app


def make_client(path="/lol-game-data/assets/v1/champion-icons/266.png", alias="Aatrox"):
    client = Mock()
    client.champion_summary.return_value.json.return_value = [{"id": 266, "alias": alias, "squarePortraitPath": path}]
    client.asset.return_value.status_code = 200
    client.asset.return_value.content = PNG_SIGNATURE + b"portrait"
    return client


def test_portrait_route_serves_png_and_reuses_cached_bytes():
    source = make_client()
    with TestClient(create_app(league_client=source)) as api:
        first = api.get("/champions/266/portrait")
        second = api.get("/champions/266/portrait")
    assert first.status_code == second.status_code == 200
    assert first.content == second.content == PNG_SIGNATURE + b"portrait"
    assert first.headers["content-type"] == "image/png"
    assert first.headers["cache-control"] == "private, max-age=300"
    assert first.headers["x-content-type-options"] == "nosniff"
    source.asset.assert_called_once_with("/lol-game-data/assets/v1/champion-icons/266.png")
    source.champion_summary.assert_called_once()


@pytest.mark.parametrize("path", [
    "https://example.test/266.png", "/lol-login/v1/session", "/lol-game-data/assets/v1/champion-icons/17.png",
    "/lol-game-data/assets/v1/champion-icons/../266.png", "/lol-game-data/assets/v1/champion-icons/266.png?private=1",
])
def test_portrait_metadata_cannot_redirect_to_other_assets(path):
    source = make_client(path)
    with TestClient(create_app(league_client=source)) as api:
        assert api.get("/champions/266/portrait").status_code == 404
    source.asset.assert_not_called()


def test_unknown_ids_and_mode_variants_do_not_fetch_assets():
    source = make_client(alias="Jade_Aatrox")
    with TestClient(create_app(league_client=source)) as api:
        missing = api.get("/champions/999999/portrait")
        assert missing.status_code == 404
        assert missing.headers["cache-control"] == "no-store"
        assert api.get("/champions/266/portrait").status_code == 404
        assert api.get("/champions/0/portrait").status_code == 422
    source.asset.assert_not_called()


def test_invalid_image_is_not_cached_and_can_recover():
    source = make_client()
    source.asset.return_value.content = b"<html>not an image</html>"
    query = ChampionPortraitQuery(source)
    assert query.portrait(266) is None
    source.asset.return_value.content = PNG_SIGNATURE + b"recovered"
    assert query.portrait(266) == PNG_SIGNATURE + b"recovered"
    assert source.asset.call_count == 2


def test_cache_expires_and_source_failure_can_retry():
    source = make_client()
    now = [0.0]
    query = ChampionPortraitQuery(source, clock=lambda: now[0])
    first = query.portrait(266)
    now[0] = 301
    source.asset.return_value.content = PNG_SIGNATURE + b"new patch"
    assert query.portrait(266) != first
    assert source.asset.call_count == 2
    source.champion_summary.side_effect = OSError("offline")
    now[0] = 602
    with TestClient(create_app(league_client=source)) as api:
        assert api.get("/champions/266/portrait").status_code == 503
        source.champion_summary.side_effect = None
        assert api.get("/champions/266/portrait").status_code == 200
