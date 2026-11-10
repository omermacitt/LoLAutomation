"""Exercise default application services through an injected native LCU adapter."""

from unittest.mock import Mock

from fastapi.testclient import TestClient

from rune_pilot.application.config_service import ConfigService
from rune_pilot.composition.api_app import create_app
from rune_pilot.infrastructure.config_repository import ConfigRepository
from rune_pilot.infrastructure.league_client_adapter import LcuLeagueClient
from rune_pilot.infrastructure.rune_data_provider import JsonRuneData


def test_factory_wires_query_services_to_supplied_league_client(tmp_path):
    summary = [
        {"id": 2, "name": "Olaf", "alias": "Olaf"},
        {"id": 1, "name": "Annie", "alias": "Annie"},
    ]
    owned = [
        {**summary[0], "ownership": {"owned": False}},
        {**summary[1], "ownership": {"owned": True}},
    ]
    data = {
        "/lol-game-data/assets/v1/champion-summary.json": summary,
        "/lol-champions/v1/owned-champions-minimal": owned,
        "/lol-gameflow/v1/gameflow-phase": "ChampSelect",
        "/lol-game-data/assets/v1/champions/1.json": {
            "skins": [{"id": 1000, "name": "Annie"}, {"id": 1001, "name": "Goth"}]
        },
        "/lol-inventory/v2/inventory/CHAMPION_SKIN": [
            {"itemId": 1001, "owned": True},
            {"itemId": 2001, "owned": True},
        ],
        "/lol-perks/v1/styles": [{"id": 8000}],
        "/lol-perks/v1/perks": [{"id": 8005, "iconPath": "perk-images/attack.png"}],
        "/lol-game-data/assets/v1/perk-images/attack.png": b"png",
    }

    def read(method, path):
        assert method == "GET"
        result = Mock(status_code=200, content=data[path])
        result.json.return_value = data[path]
        return result

    app = create_app(
        league_client=LcuLeagueClient(read),
        rune_source=JsonRuneData(str(tmp_path / "missing.json")),
        config_service=ConfigService(ConfigRepository(str(tmp_path / "settings.json"))),
    )
    with TestClient(app) as client:
        assert client.get("/champions").json() == [{"id": 1, "name": "Annie", "alias": "Annie"}]
        catalog = client.get("/champion-catalog").json()
        assert [item["id"] for item in catalog["all_champions"]] == [1, 2]
        assert [item["id"] for item in catalog["pickable_champions"]] == [1]
        assert client.get("/gameflow").json() == {"phase": "ChampSelect"}
        assert client.get("/champions/1/skins").json()["skins"] == [
            {"id": 1000, "name": "Default (Annie)"},
            {"id": 1001, "name": "Goth"},
        ]
        assert client.get("/runes/catalog").json()["styles"] == [{"id": 8000}]
        assert client.get("/runes/icons/8005").content == b"png"
        assert client.get("/health").json()["running"] is False


def test_factory_instances_do_not_share_metadata_caches(tmp_path):
    apps = []
    for name in ("Annie", "Localized Annie"):
        league = Mock()
        league.champion_summary.return_value = Mock(status_code=200)
        league.champion_summary.return_value.json.return_value = [
            {"id": 1, "name": name, "alias": "Annie"}
        ]
        apps.append(create_app(league_client=league))
    assert apps[0].state.champions.get_champion_name_by_id(1) == "Annie"
    assert apps[1].state.champions.get_champion_name_by_id(1) == "Localized Annie"
    assert apps[0].state.champions.get_champion_name_by_id(1) == "Annie"
