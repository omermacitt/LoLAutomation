"""Known skin artwork only; bounded caching, optional images, retryable failures."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from rune_pilot.application import skin_artwork_query as module
from rune_pilot.application.skin_artwork_query import SkinArtworkQuery
from rune_pilot.composition.api_app import create_app

PATH = (
    "/lol-game-data/assets/ASSETS/Characters/Aatrox/Skins/Base/Images/aatrox_splash_centered_0.jpg"
)
JPEG = b"\xff\xd8\xffimage"


def source_for(path=PATH):
    source = Mock()
    source.champion_data.return_value.status_code = 200
    source.champion_data.return_value.json.return_value = {
        "id": 266,
        "alias": "Aatrox",
        "skins": [{"id": 266000, "splashPath": path}, {"id": 266001, "splashPath": PATH}],
    }
    source.asset.return_value.status_code = 200
    source.asset.return_value.content = JPEG
    return source


def test_artwork_endpoint_uses_known_metadata_and_caches_jpeg():
    source = source_for()
    with TestClient(create_app(league_client=source)) as api:
        first = api.get("/champions/266/skins/266000/artwork")
        second = api.get("/champions/266/skins/266000/artwork")
    assert first.status_code == second.status_code == 200
    assert first.content == JPEG
    assert first.headers["content-type"] == "image/jpeg"
    assert first.headers["cache-control"] == "private, max-age=300"
    assert first.headers["x-content-type-options"] == "nosniff"
    source.champion_data.assert_called_once_with(266)
    source.asset.assert_called_once_with(PATH)


@pytest.mark.parametrize(
    "path",
    [
        "https://example.test/skin.jpg",
        "/lol-login/v1/session",
        PATH + "?token=secret",
        PATH.replace("Base", ".."),
        PATH.replace("/Base/", "/%2e%2e/"),
        PATH.replace("/", "\\"),
    ],
)
def test_metadata_does_not_allow_remote_or_arbitrary_lcu_paths(path):
    source = source_for(path)
    with TestClient(create_app(league_client=source)) as api:
        response = api.get("/champions/266/skins/266000/artwork")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
    source.asset.assert_not_called()


def test_unknown_skin_and_wrong_champion_never_fetch_assets():
    source = source_for()
    query = SkinArtworkQuery(source)
    assert query.artwork(266, 17000) is None
    source.champion_data.assert_not_called()
    assert query.artwork(266, 266999) is None
    source.asset.assert_not_called()
    source.champion_data.return_value.json.return_value["alias"] = "Jade_Aatrox"
    assert SkinArtworkQuery(source).artwork(266, 266000) is None
    source.asset.assert_not_called()


def test_invalid_or_oversized_images_are_not_cached_and_can_retry(monkeypatch):
    source = source_for()
    query = SkinArtworkQuery(source)
    source.asset.return_value.content = b"<html>missing</html>"
    assert query.artwork(266, 266000) is None
    monkeypatch.setattr(module, "MAX_IMAGE_BYTES", 8)
    source.asset.return_value.content = JPEG + b"excessive"
    assert query.artwork(266, 266000) is None
    source.asset.return_value.content = JPEG
    assert query.artwork(266, 266000) == (JPEG, "image/jpeg")
    assert source.asset.call_count == 3


def test_cache_expires_and_limits_total_bytes_and_entries(monkeypatch):
    source = source_for()
    source.champion_data.return_value.json.return_value["skins"] += [
        {"id": 266002, "splashPath": PATH}
    ]
    now = [0.0]
    query = SkinArtworkQuery(source, clock=lambda: now[0])
    monkeypatch.setattr(module, "MAX_CACHED_IMAGES", 2)
    monkeypatch.setattr(module, "MAX_CACHE_BYTES", len(JPEG) * 2)
    for sid in (266000, 266001, 266002):
        assert query.artwork(266, sid)
    assert query.artwork(266, 266000)
    assert source.asset.call_count == 4  # LRU eviction.
    monkeypatch.setattr(module, "MAX_CACHE_BYTES", len(JPEG))
    assert query.artwork(266, 266001)
    assert query._bytes <= len(JPEG)
    assert len(query._images) == 1
    now[0] = 301
    assert query.artwork(266, 266001)
    assert source.champion_data.call_count == 2


def test_source_failure_is_retryable_503_and_missing_assets_404():
    source = source_for()
    source.champion_data.side_effect = OSError("private failure")
    with TestClient(create_app(league_client=source)) as api:
        response = api.get("/champions/266/skins/266000/artwork")
        assert response.status_code == 503
        assert "private failure" not in response.text
        source.champion_data.side_effect = None
        source.asset.return_value.status_code = 404
        assert api.get("/champions/266/skins/266000/artwork").status_code == 404
        source.asset.return_value.status_code = 200
        assert api.get("/champions/266/skins/266000/artwork").status_code == 200


@pytest.mark.parametrize(
    "path", ["/champions/0/skins/17000/artwork", "/champions/17/skins/0/artwork"]
)
def test_nonpositive_identifiers_rejected(path):
    with TestClient(create_app(league_client=source_for())) as api:
        assert api.get(path).status_code == 422
