"""
Faz 2 infrastructure/domain modüllerinin testleri: kaynak yolları, şampiyon slug'ı
ve ChampionRepo cache/sahiplik mantığı (LCU mock'lanır).
"""

import os

from runepilot.domain.champions import champion_slug_from_alias
from runepilot.infrastructure import champion_repo as champion_repo_module
from runepilot.infrastructure.champion_repo import ChampionRepo
from runepilot.infrastructure.resource_paths import resource_path


class _FakeResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


# --- resource_path ------------------------------------------------------------
def test_resource_path_resolves_bundled_runes_json():
    path = resource_path("runes.json")
    assert os.path.isabs(path)
    assert os.path.exists(path)  # proje kökü doğru hesaplanmalı


# --- domain: champion_slug_from_alias -----------------------------------------
def test_domain_champion_slug():
    assert champion_slug_from_alias("MonkeyKing") == "wukong"
    assert champion_slug_from_alias("Annie") == "annie"
    assert champion_slug_from_alias("") == ""


# --- ChampionRepo -------------------------------------------------------------
def test_champion_repo_slug_and_name_cache(monkeypatch):
    summary = [
        {"id": 1, "name": "Annie", "alias": "Annie"},
        {"id": 62, "name": "Wukong", "alias": "MonkeyKing"},
    ]
    monkeypatch.setattr(
        champion_repo_module, "lcu_request", lambda *a, **k: _FakeResp(200, summary)
    )
    repo = ChampionRepo()
    assert repo.get_slug_by_id(1) == "annie"
    assert repo.get_slug_by_id(62) == "wukong"  # özel alias
    # Ad cache'i slug çözümlemesi sırasında dolar.
    assert repo.get_name_by_id(1) == "Annie"


def test_champion_repo_load_owned_filters(monkeypatch):
    owned = [
        {"id": 1, "name": "Annie", "alias": "Annie", "ownership": {"owned": True}},
        {"id": 2, "name": "Olaf", "alias": "Olaf", "ownership": {"owned": False}},
        {"id": 0, "name": "Gecersiz"},
    ]
    monkeypatch.setattr(champion_repo_module, "lcu_request", lambda *a, **k: _FakeResp(200, owned))
    repo = ChampionRepo()
    result = repo.load_owned_map()
    assert set(result.keys()) == {1}  # sahip olunmayan (Olaf) ve id<=0 elenmeli
    assert result[1] == {"id": 1, "name": "Annie", "alias": "Annie"}


def test_champion_repo_non_200_returns_empty(monkeypatch):
    monkeypatch.setattr(champion_repo_module, "lcu_request", lambda *a, **k: _FakeResp(404, None))
    repo = ChampionRepo()
    assert repo.get_slug_by_id(1) is None
    assert repo.load_owned_map() == {}
