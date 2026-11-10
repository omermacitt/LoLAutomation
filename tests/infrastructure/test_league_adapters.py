"""LCU commands retain their native routes and payloads after port extraction."""

import json
from unittest.mock import Mock

import pytest

from rune_pilot.infrastructure.league_client_adapter import LcuLeagueClient
from rune_pilot.infrastructure.rune_data_provider import JsonRuneData


@pytest.mark.parametrize(
    "operation,args,kwargs,expected",
    [
        ("create_lobby", (420,), {}, ("POST", "/lol-lobby/v2/lobby", {"queueId": 420})),
        (
            "complete_action",
            (12, 1),
            {},
            (
                "PATCH",
                "/lol-champ-select/v1/session/actions/12",
                {"championId": 1, "completed": True},
            ),
        ),
        (
            "set_selection",
            ({"spell1Id": 4, "selectedSkinId": 1001},),
            {},
            (
                "PATCH",
                "/lol-champ-select/v1/session/my-selection",
                {"spell1Id": 4, "selectedSkinId": 1001},
            ),
        ),
        ("accept_ready_check", (), {}, ("POST", "/lol-matchmaking/v1/ready-check/accept")),
        (
            "update_rune_page",
            (3, {"current": True}),
            {},
            ("PUT", "/lol-perks/v1/pages/3", {"current": True}),
        ),
        ("delete_rune_page", (3,), {}, ("DELETE", "/lol-perks/v1/pages/3")),
        ("champion_data", (1,), {}, ("GET", "/lol-game-data/assets/v1/champions/1.json")),
        ("perks", (), {"game_data": True}, ("GET", "/lol-game-data/assets/v1/perks.json")),
    ],
)
def test_lcu_command_mapping(operation, args, kwargs, expected):
    request = Mock()
    result = getattr(LcuLeagueClient(request), operation)(*args, **kwargs)
    request.assert_called_once_with(*expected)
    assert result is request.return_value


def test_json_recommendations_are_lazy_cached_defensive_and_instance_owned(tmp_path):
    path = tmp_path / "runes.json"
    source = JsonRuneData(str(path))
    path.write_text(json.dumps({"1": {"selectedPerkIds": [1, 2]}}), encoding="utf-8")
    first = source.get_runes_data()
    first["1"]["selectedPerkIds"].clear()
    path.write_text(json.dumps({"2": {}}), encoding="utf-8")
    assert source.get_runes_data() == {"1": {"selectedPerkIds": [1, 2]}}
    assert JsonRuneData(str(path)).get_runes_data() == {"2": {}}


@pytest.mark.parametrize("raw", [None, "invalid", "[]"])
def test_missing_or_invalid_json_is_an_empty_recommendation_source(tmp_path, raw):
    path = tmp_path / "runes.json"
    if raw is not None:
        path.write_text(raw, encoding="utf-8")
    assert JsonRuneData(str(path)).get_runes_data() == {}
