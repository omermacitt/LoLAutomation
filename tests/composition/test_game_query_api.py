"""Source-backed query contracts, unavailable sources, and binary icons."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from rune_pilot.application.game_query_service import GameQueryService
from rune_pilot.composition.api_app import create_app
from rune_pilot.domain.game_data import SkinCatalog


@pytest.fixture
def sources():
    return SimpleNamespace(
        summary=[
            {"id": 266, "name": "Aatrox"},
            {"id": 1, "name": "Annie"},
            {"id": 2, "name": "Olaf"},
        ],
        owned=[
            {"id": 266, "name": "Aatrox", "ownership": {"owned": True}},
            {"id": 1, "name": "Annie", "ownership": {"owned": False}, "freeToPlay": True},
            {"id": 2, "name": "Olaf", "ownership": {"owned": False}},
        ],
        phase="ChampSelect",
        names={266000: "Aatrox", 266001: "Justicar", 266002: "Mecha"},
        skins={266002, 266001, 266000, 1001},
        styles=[{"id": 8000, "name": "Precision"}],
        perks=[{"id": 8005, "name": "Press the Attack", "iconPath": "perk-images/attack.png"}],
        icon=b"png bytes",
        icon_paths=[],
    )


def service_for(sources):
    def icon(path):
        sources.icon_paths.append(path)
        return sources.icon

    return GameQueryService(
        champion_summary=lambda: sources.summary,
        owned_champions=lambda: sources.owned,
        gameflow_phase=lambda: sources.phase,
        skin_options=lambda cid: SkinCatalog(sources.names, sources.skins),
        perk_styles=lambda: sources.styles,
        perks=lambda: sources.perks,
        perk_icon=icon,
    )


def test_catalog_separates_ban_and_pick_eligibility(sources):
    with TestClient(create_app(game_queries=service_for(sources))) as client:
        response = client.get("/champion-catalog")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["all_champions"]] == [266, 1, 2]
    assert [item["id"] for item in response.json()["pickable_champions"]] == [266, 1]


def test_classic_variants_do_not_duplicate_normal_pick_and_ban_options(sources):
    jade = {"id": 60266, "name": "Aatrox", "alias": "Jade_Aatrox", "ownership": {"owned": True}}
    sources.summary.insert(0, jade)
    sources.owned.insert(0, jade)
    with TestClient(create_app(game_queries=service_for(sources))) as client:
        catalog = client.get("/champion-catalog").json()
    for field in ("all_champions", "pickable_champions"):
        assert [row["id"] for row in catalog[field] if row["name"] == "Aatrox"] == [266]


def test_variant_ownership_does_not_make_the_normal_champion_pickable(sources):
    sources.owned = [
        {"id": 60266, "name": "Aatrox", "alias": "Jade_Aatrox", "ownership": {"owned": True}}
    ]
    with TestClient(create_app(game_queries=service_for(sources))) as client:
        catalog = client.get("/champion-catalog").json()
    assert catalog["pickable_champions"] == []
    assert any(row["id"] == 266 for row in catalog["all_champions"])


def test_empty_ownership_does_not_offer_unowned_champions(sources):
    sources.owned = []
    with TestClient(create_app(game_queries=service_for(sources))) as client:
        response = client.get("/champion-catalog")
    assert response.status_code == 200
    assert response.json()["pickable_champions"] == []


def test_ownership_failure_is_503_instead_of_empty_or_all_champions(sources):
    service = service_for(sources)

    def unavailable():
        raise OSError("LCU disconnected")

    service._owned_champions = unavailable
    with TestClient(create_app(game_queries=service)) as client:
        response = client.get("/champion-catalog")
    assert response.status_code == 503


def test_gameflow_including_disconnected_state(sources):
    with TestClient(create_app(game_queries=service_for(sources))) as client:
        assert client.get("/gameflow").json() == {"phase": "ChampSelect"}
        sources.phase = None
        assert client.get("/gameflow").json() == {"phase": None}


def test_skins_include_default_and_only_owned_skins_for_this_champion(sources):
    with TestClient(create_app(game_queries=service_for(sources))) as client:
        response = client.get("/champions/266/skins")
    assert response.status_code == 200
    assert response.json() == {
        "champion_id": 266,
        "skins": [
            {"id": 266000, "name": "Default (Aatrox)"},
            {"id": 266001, "name": "Justicar"},
            {"id": 266002, "name": "Mecha"},
        ],
    }


def test_rune_catalog_and_binary_icon(sources):
    with TestClient(create_app(game_queries=service_for(sources))) as client:
        assert client.get("/runes/catalog").json() == {
            "styles": sources.styles,
            "perks": sources.perks,
        }
        response = client.get("/runes/icons/8005")
        assert response.status_code == 200
        assert response.content == sources.icon
        assert response.headers["content-type"] == "image/png"
        assert client.get("/runes/icons/9999").status_code == 404
    assert sources.icon_paths == ["/lol-game-data/assets/v1/perk-images/attack.png"]


@pytest.mark.parametrize(
    "path",
    [
        "https://example.test/icon.png",
        "/lol-login/v1/session",
        "../private",
        "a\\b.png",
        "icon.png?x=1",
    ],
)
def test_icon_route_does_not_accept_arbitrary_or_remote_lcu_paths(sources, path):
    sources.perks[0]["iconPath"] = path
    with TestClient(create_app(game_queries=service_for(sources))) as client:
        assert client.get("/runes/icons/8005").status_code == 404
    assert not sources.icon_paths


@pytest.mark.parametrize("url", ["/champions/0/skins", "/champions/-1/skins", "/runes/icons/0"])
def test_nonpositive_ids_are_rejected(sources, url):
    with TestClient(create_app(game_queries=service_for(sources))) as client:
        assert client.get(url).status_code == 422


@pytest.mark.parametrize(
    "field,url",
    [("summary", "/champion-catalog"), ("styles", "/runes/catalog"), ("perks", "/runes/catalog")],
)
def test_incomplete_catalogs_report_unavailable(sources, field, url):
    setattr(sources, field, [])
    with TestClient(create_app(game_queries=service_for(sources))) as client:
        assert client.get(url).status_code == 503
