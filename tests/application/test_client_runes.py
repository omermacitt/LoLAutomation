"""Client recommendations never fall back to another position or a web dataset."""

from copy import deepcopy
from unittest.mock import Mock

import pytest

from rune_pilot.application.game_query_service import QueryUnavailable
from rune_pilot.application.rune_service import RuneService
from rune_pilot.domain.league_runes import recommendation_pages
from rune_pilot.infrastructure.league_client_adapter import LcuLeagueClient


def suggestion(role="JUNGLE", champion=106):
    return {
        "recommendationChampionId": champion,
        "position": role,
        "isDefaultPosition": True,
        "primaryPerkStyleId": 8000,
        "secondaryPerkStyleId": 8200,
        "perks": [{"id": rid} for rid in [8005, 9111, 9105, 8299, 8234, 8232, 5005, 5008, 5001]],
        "summonerSpellIds": [4, 14],
    }


def test_mixed_client_response_filters_champion_and_role_without_trusting_default_flag():
    first, second = suggestion(), suggestion()
    second["perks"][0]["id"] = 8008
    raw = [suggestion("TOP"), first, second, suggestion(champion=1), None]
    before = deepcopy(raw)
    result = recommendation_pages(raw, 106, "JUNGLE")
    assert len(result) == 2
    assert [page["selectedPerkIds"][0] for page in result] == [8005, 8008]
    assert "summonerSpellIds" not in result[0]
    assert raw == before
    assert recommendation_pages(raw, 106, "MIDDLE") == []


@pytest.mark.parametrize(
    "role,map_id", [("", 11), ("FILL", 11), ("SUPPORT", 11), ("jungle", 11), ("JUNGLE", 12)]
)
def test_unknown_role_or_unsupported_map_does_not_query_or_guess(role, map_id):
    client = Mock()
    assert RuneService(client).get_recommended_pages(106, role, map_id) == []
    client.recommended_runes.assert_not_called()


@pytest.mark.parametrize("role", ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"])
def test_recommendation_operation_is_one_exact_role_get(role):
    request = Mock()
    request.return_value.status_code = 200
    request.return_value.json.return_value = [suggestion(role)]
    result = RuneService(LcuLeagueClient(request)).get_recommended_pages(106, role)
    assert len(result) == 1
    request.assert_called_once_with(
        "GET", f"/lol-perks/v1/recommended-pages/champion/106/position/{role}/map/11"
    )


@pytest.mark.parametrize("status,raw", [(404, []), (500, []), (200, {}), (200, None)])
def test_transport_and_schema_errors_are_unavailable_not_successful_empty_lists(status, raw):
    client = Mock()
    client.recommended_runes.return_value.status_code = status
    client.recommended_runes.return_value.json.return_value = raw
    with pytest.raises(QueryUnavailable):
        RuneService(client).get_recommended_pages(106, "JUNGLE")


def test_disconnection_is_sanitized_and_retry_fetches_fresh_data():
    client = Mock()
    client.recommended_runes.side_effect = OSError("private lockfile details")
    service = RuneService(client)
    with pytest.raises(QueryUnavailable, match="League rune recommendations") as error:
        service.get_recommended_pages(106, "JUNGLE")
    assert "private" not in str(error.value)
    client.recommended_runes.side_effect = None
    client.recommended_runes.return_value.status_code = 200
    client.recommended_runes.return_value.json.return_value = []
    assert service.get_recommended_pages(106, "JUNGLE") == []
    client.recommended_runes.return_value.json.return_value = [suggestion()]
    assert service.get_recommended_pages(106, "JUNGLE")
