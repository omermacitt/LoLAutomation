"""Strict UI queries distinguish an unavailable source from empty ownership."""

from unittest.mock import Mock

import pytest
import requests

from rune_pilot.application import champion_query, perk_query, skin_query
from rune_pilot.infrastructure import lcu_client


def test_legacy_champion_list_and_name_cache_exclude_classic_variants():
    normal = {"id": 266, "name": "Aatrox", "alias": "Aatrox", "ownership": {"owned": True}}
    variant = {"id": 60266, "name": "Aatrox", "alias": "Jade_Aatrox", "ownership": {"owned": True}}
    response = Mock(status_code=200)
    response.json.return_value = [variant, normal]
    client = Mock()
    client.owned_champions.return_value = response
    client.champion_summary.return_value = response
    query = champion_query.ChampionQuery(client)
    assert [row["id"] for row in query.get_champions()] == [266]
    assert query.get_champion_slug_by_id(266) == "aatrox"
    assert query.get_champion_slug_by_id(60266) is None


@pytest.mark.parametrize("name,operation", [("get_champion_summary", "champion_summary"), ("get_owned_champions_raw", "owned_champions")])
def test_strict_champion_reads_report_bad_responses(name, operation):
    response = Mock(status_code=500)
    response.raise_for_status.side_effect = requests.HTTPError("unavailable")
    client = Mock()
    getattr(client, operation).return_value = response
    reader = getattr(champion_query.ChampionQuery(client), name)
    assert reader() == []  # Existing automation callers retain their tolerant API.
    with pytest.raises(requests.HTTPError):
        reader(strict=True)


def test_strict_skin_query_does_not_turn_inventory_failure_into_default_only():
    champion = Mock(status_code=200)
    champion.json.return_value = {"skins": [{"id": 266000, "name": "Aatrox"}]}
    failed = Mock(status_code=500)
    failed.raise_for_status.side_effect = requests.HTTPError("inventory unavailable")
    client = Mock()
    client.champion_data.return_value = champion
    client.skin_inventory.return_value = failed
    with pytest.raises(requests.HTTPError):
        skin_query.SkinQuery(client).get_skin_options_for_champion(266, strict=True)


def test_perk_fallback_endpoint_still_works():
    missing = Mock()
    missing.raise_for_status.side_effect = requests.HTTPError("not found")
    valid = Mock()
    valid.json.return_value = {"perks": [{"id": 8005}]}
    query = Mock(side_effect=[missing, valid])
    client = Mock()
    client.perks = query
    assert perk_query.PerkQuery(client).get_perks() == [{"id": 8005}]
    assert query.call_args.kwargs == {"game_data": True}


def test_lcu_calls_have_a_timeout(monkeypatch):
    monkeypatch.setattr(lcu_client, "get_lcu_credentials", lambda: ("1", "test"))
    request = Mock()
    monkeypatch.setattr(lcu_client.requests, "request", request)
    lcu_client.lcu_request("GET", "/lol-gameflow/v1/gameflow-phase")
    assert request.call_args.kwargs["timeout"] == 2.0


def test_champion_metadata_retries_failure_and_is_cached_per_instance():
    failed = Mock(status_code=503)
    first_response = Mock(status_code=200)
    first_response.json.return_value = [{"id": 62, "name": "Wukong", "alias": "MonkeyKing"}]
    second_response = Mock(status_code=200)
    second_response.json.return_value = [{"id": 62, "name": "Different name", "alias": "Different"}]
    first_client, second_client = Mock(), Mock()
    first_client.champion_summary.side_effect = [failed, first_response]
    second_client.champion_summary.return_value = second_response
    first = champion_query.ChampionQuery(first_client)
    second = champion_query.ChampionQuery(second_client)
    assert first.get_champion_slug_by_id(62) is None
    assert first.get_champion_slug_by_id(62) == "wukong"
    assert first.get_champion_name_by_id(62) == "Wukong"
    assert second.get_champion_name_by_id(62) == "Different name"
    assert first.get_champion_name_by_id(62) == "Wukong"
    assert first_client.champion_summary.call_count == 2


def test_perk_style_failure_can_retry_and_success_does_not_leak_between_instances():
    failed = Mock()
    failed.raise_for_status.side_effect = OSError("disconnected")
    valid = Mock()
    valid.json.return_value = [{"id": 8000}]
    other = Mock()
    other.json.return_value = [{"id": 8100}]
    first_client, second_client = Mock(), Mock()
    first_client.perk_styles.side_effect = [failed, valid]
    second_client.perk_styles.return_value = other
    first = perk_query.PerkQuery(first_client)
    with pytest.raises(OSError):
        first.get_perk_styles()
    assert first.get_perk_styles() == [{"id": 8000}]
    assert perk_query.PerkQuery(second_client).get_perk_styles() == [{"id": 8100}]
    assert first.get_perk_styles() == [{"id": 8000}]
    assert first_client.perk_styles.call_count == 2
