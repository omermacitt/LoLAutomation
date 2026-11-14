"""Nested League chromas keep localized names, ownership and exact selection IDs."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from rune_pilot.application.skin_query import SkinQuery
from rune_pilot.composition.api_app import create_app


@pytest.mark.parametrize("count", [4, 6])
def test_owned_nested_chromas_are_named_without_changing_ids(count):
    names = ["Deniz Mavisi", "Yakut", "Zümrüt", "Tanzanit", "Test rengi 5", "Test rengi 6"]
    chromas = [
        {"id": 107004 + index, "name": f"Kelle Avcısı Rengar ({name})"}
        for index, name in enumerate(names[:count])
    ]
    source = Mock()
    source.champion_data.return_value.status_code = 200
    source.champion_data.return_value.json.return_value = {
        "id": 107,
        "skins": [
            {"id": 107000, "name": "Rengar"},
            {"id": 107001, "name": "Kelle Avcısı Rengar", "chromas": chromas},
        ],
    }
    source.skin_inventory.return_value.status_code = 200
    source.skin_inventory.return_value.json.return_value = [
        {"itemId": sid, "owned": True} for sid in [107001, *[c["id"] for c in chromas]]
    ] + [{"itemId": 107099, "owned": False}, {"itemId": 266001, "owned": True}]
    with TestClient(create_app(league_client=source)) as api:
        response = api.get("/champions/107/skins")
    assert response.status_code == 200
    assert response.json()["skins"] == [
        {"id": 107000, "name": "Default (Rengar)"},
        {"id": 107001, "name": "Kelle Avcısı Rengar"},
        *[{**chroma, "parent_skin_id": 107001} for chroma in chromas],
    ]


@pytest.mark.parametrize("chromas", [None, {}, "invalid", [None, {}, {"id": "bad"}]])
def test_malformed_optional_chromas_do_not_hide_owned_parent_skin(chromas):
    source = Mock()
    source.champion_data.return_value.status_code = 200
    source.champion_data.return_value.json.return_value = {
        "skins": [{"id": 107001, "name": "Kelle Avcısı Rengar", "chromas": chromas}]
    }
    source.skin_inventory.return_value.status_code = 200
    source.skin_inventory.return_value.json.return_value = [{"itemId": 107001, "owned": True}]
    catalog = SkinQuery(source).get_skin_options_for_champion(107, strict=True)
    assert catalog.names[107001] == "Kelle Avcısı Rengar"
    assert catalog.owned == {107001}
    assert catalog.chroma_parents == {}


@pytest.mark.parametrize("parent_owned", [True, False])
def test_chroma_options_require_owned_color_and_available_parent(parent_owned):
    source = Mock()
    source.champion_data.return_value.status_code = 200
    source.champion_data.return_value.json.return_value = {
        "skins": [
            {"id": 107000, "name": "Rengar"},
            {
                "id": 107001,
                "name": "Kelle Avcısı Rengar",
                "chromas": [
                    {"id": 107004, "name": "Deniz Mavisi"},
                    {"id": 107005, "name": "Yakut"},
                    {"id": 266004, "name": "Wrong champion"},
                ],
            },
        ]
    }
    source.skin_inventory.return_value.status_code = 200
    source.skin_inventory.return_value.json.return_value = [
        {"itemId": 107001, "owned": parent_owned},
        {"itemId": 107004, "owned": True},
        {"itemId": 107005, "owned": False},
    ]
    with TestClient(create_app(league_client=source)) as api:
        response = api.get("/champions/107/skins")
    assert response.status_code == 200
    rows = response.json()["skins"]
    assert [row["id"] for row in rows] == ([107000, 107001, 107004] if parent_owned else [107000])
    if parent_owned:
        assert rows[-1]["parent_skin_id"] == 107001
