"""
Faz 2 infrastructure/domain modüllerinin testleri: kaynak yolları, şampiyon slug'ı
ve ChampionRepo cache/sahiplik mantığı (LCU mock'lanır).
"""

import os
from unittest.mock import Mock

from rune_pilot.application.champion_query import ChampionQuery
from rune_pilot.domain.champion_service import champion_slug_from_alias
from rune_pilot.shared.resource import resource_path


class _FakeResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


# --- resource_path ------------------------------------------------------------
def test_resource_path_resolves_desktop_route_policy():
    path = resource_path("src/rune_pilot/composition/desktop_routes.json")
    assert os.path.isabs(path)
    assert os.path.exists(path)  # proje kökü doğru hesaplanmalı


# --- domain: champion_slug_from_alias -----------------------------------------
def test_domain_champion_slug():
    assert champion_slug_from_alias("MonkeyKing") == "wukong"
    assert champion_slug_from_alias("Annie") == "annie"
    assert champion_slug_from_alias("") == ""


# --- ChampionRepo -------------------------------------------------------------
def test_champion_repo_slug_and_name_cache():
    summary = [
        {"id": 1, "name": "Annie", "alias": "Annie"},
        {"id": 62, "name": "Wukong", "alias": "MonkeyKing"},
    ]
    client = Mock()
    client.champion_summary.return_value = _FakeResp(200, summary)
    repo = ChampionQuery(client)
    assert repo.get_champion_slug_by_id(1) == "annie"
    assert repo.get_champion_slug_by_id(62) == "wukong"  # özel alias
    # Ad cache'i slug çözümlemesi sırasında dolar.
    assert repo.get_champion_name_by_id(1) == "Annie"


def test_champion_repo_load_owned_filters():
    owned = [
        {"id": 1, "name": "Annie", "alias": "Annie", "ownership": {"owned": True}},
        {"id": 2, "name": "Olaf", "alias": "Olaf", "ownership": {"owned": False}},
        {"id": 0, "name": "Gecersiz"},
    ]
    client = Mock()
    client.owned_champions.return_value = _FakeResp(200, owned)
    repo = ChampionQuery(client)
    result = repo.load_champions_map()
    assert set(result.keys()) == {1}  # sahip olunmayan (Olaf) ve id<=0 elenmeli
    assert result[1] == {"id": 1, "name": "Annie", "alias": "Annie"}


def test_champion_repo_non_200_returns_empty():
    client = Mock()
    client.champion_summary.return_value = _FakeResp(404, None)
    client.owned_champions.return_value = _FakeResp(404, None)
    repo = ChampionQuery(client)
    assert repo.get_champion_slug_by_id(1) is None
    assert repo.load_champions_map() == {}
