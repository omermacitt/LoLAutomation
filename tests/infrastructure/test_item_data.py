"""Mode eligibility uses game shop references, never names or ID ranges."""

from copy import deepcopy
from unittest.mock import Mock

import pytest

from rune_pilot.infrastructure.item_data import DragonItemData, classic_item_ids


def map_fixture():
    return {
        "Maps/Shipping/Map11/Modes/CLASSIC": {
            "__type": "GameModeMapData",
            "itemLists": ["{base}", "{champion}"],
        },
        "Maps/Shipping/Map11/Modes/SWIFTPLAY": {
            "__type": "GameModeMapData",
            "itemLists": ["{swiftplay}"],
        },
        "{base}": {"__type": "GameModeItemList", "mItems": ["Items/3190", "Items/3078"]},
        "{champion}": {"__type": "GameModeItemList", "mItems": ["Items/3599", "Items/3600"]},
        "{swiftplay}": {
            "__type": "GameModeItemList",
            "mItems": ["Items/2051", "Items/3112", "Items/3177", "Items/3184", "Items/323190"],
        },
    }


def test_resolves_only_classic_lists_preserving_distinct_same_name_items():
    assert classic_item_ids(map_fixture()) == {"3190", "3078", "3599", "3600"}


@pytest.mark.parametrize("failure", ["mode", "reference", "type", "paths", "path", "empty"])
def test_incomplete_mode_data_fails_instead_of_falling_back_to_maps_flag(failure):
    data = map_fixture()
    if failure == "mode":
        del data["Maps/Shipping/Map11/Modes/CLASSIC"]
    elif failure == "reference":
        del data["{base}"]
    elif failure == "type":
        data["{base}"]["__type"] = "Unknown"
    elif failure == "paths":
        data["{base}"]["mItems"] = None
    elif failure == "path":
        data["{base}"]["mItems"] = ["Unknown/3190"]
    else:
        data["{base}"]["mItems"] = []
        data["{champion}"]["mItems"] = []
    with pytest.raises(ValueError):
        classic_item_ids(data)


def test_catalog_excludes_wrongly_map11_flagged_items_and_caches_verified_result(monkeypatch):
    items = {
        str(i): {"name": "Same name", "maps": {"11": True}, "gold": {"purchasable": True}}
        for i in [3190, 3078, 3599, 3600, 2051, 3112, 3177, 3184, 323190]
    }
    calls = []

    def get(url, limit=None):
        calls.append(url)
        if url.endswith("realms/tr.json"):
            data = {"n": {"champion": "16.22.1", "item": "16.22.1"}}
        elif url.endswith("map11.bin.json"):
            assert "/16.22/game/" in url
            assert limit == 16 * 1024 * 1024
            data = map_fixture()
        else:
            data = {"version": "16.22.1", "data": deepcopy(items)}
        return Mock(json=Mock(return_value=data))

    source = DragonItemData()
    monkeypatch.setattr(source, "_get", get)
    result = source.catalog()
    assert set(result[2]) == {"3190", "3078", "3599", "3600"}
    assert source.catalog() is result
    assert len(calls) == 5


def test_unverified_catalog_is_not_cached_and_can_retry(monkeypatch):
    source = DragonItemData()
    replies = [
        {"n": {"champion": "16.22.1", "item": "16.22.1"}},
        {"version": "16.22.1", "data": {}},
        {"version": "16.22.1", "data": {"3078": {"name": "Trinity"}}},
        {"version": "16.22.1", "data": {}},
        {},
    ]
    monkeypatch.setattr(
        source, "_get", Mock(side_effect=[Mock(json=lambda d=d: d) for d in replies])
    )
    with pytest.raises(ValueError, match="Classic item lists unavailable"):
        source.catalog()
    assert source._catalog is None
