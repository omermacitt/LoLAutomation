"""
Rün mantığının karakterizasyon testleri.

Bu davranış Faz 3'te `domain/runes.py` + `domain/rune_naming.py`'ye taşınacak; testler
o zaman import yolunu güncelleyip aynı beklentileri koruyacak (regresyon kalkanı).
"""

import api


# --- _safe_int_list -----------------------------------------------------------
def test_safe_int_list_filters_non_ints():
    assert api._safe_int_list(["1", "2", "x", 3, None]) == [1, 2, 3]


def test_safe_int_list_non_list_returns_empty():
    assert api._safe_int_list("nope") == []
    assert api._safe_int_list(None) == []


# --- build_rune_page_name -----------------------------------------------------
def test_build_rune_page_name_simple_fits():
    assert api.build_rune_page_name(prefix="Auto", champion_name="Annie") == "Auto Annie"


def test_build_rune_page_name_strips_punctuation_and_spaces():
    # "Aurelion Sol" -> compact "AurelionSol"; "Auto AurelionSol" == 16 char (limit).
    name = api.build_rune_page_name(prefix="Auto", champion_name="Aurelion Sol")
    assert name == "Auto AurelionSol"
    assert len(name) <= api.MAX_RUNE_PAGE_NAME_LEN


def test_build_rune_page_name_truncates_when_too_long():
    name = api.build_rune_page_name(prefix="Custom 1", champion_name="Aurelion Sol")
    assert len(name) <= api.MAX_RUNE_PAGE_NAME_LEN
    assert name.startswith("Custom 1")


def test_build_rune_page_name_defaults_on_empty():
    assert api.build_rune_page_name(prefix="", champion_name="") == "Auto Champion"


# --- get_recommended_page_for_champion : Format 1 (direct champId) -------------
def test_recommended_format1_direct_payload(monkeypatch):
    monkeypatch.setattr(
        api,
        "RUNES_DATA",
        {
            "777": {
                "primaryStyleId": 8100,
                "subStyleId": 8200,
                "selectedPerkIds": [8112, 8126, 8140, 8105, 8224, 8233, 5008, 5008, 5001],
            }
        },
    )
    page = api.get_recommended_page_for_champion(777)
    assert page == {
        "primaryStyleId": 8100,
        "subStyleId": 8200,
        "selectedPerkIds": [8112, 8126, 8140, 8105, 8224, 8233, 5008, 5008, 5001],
    }


def test_recommended_format1_rejects_wrong_perk_count(monkeypatch):
    monkeypatch.setattr(
        api,
        "RUNES_DATA",
        {"777": {"primaryStyleId": 8100, "subStyleId": 8200, "selectedPerkIds": [1, 2, 3]}},
    )
    assert api.get_recommended_page_for_champion(777) is None


# --- get_recommended_page_for_champion : Format 2 (slug -> rune_N) -------------
def test_recommended_format2_picks_highest_winrate(monkeypatch):
    monkeypatch.setattr(
        api,
        "RUNES_DATA",
        {
            "annie": {
                "rune_1": {
                    "Domination": ["8112", "8126", "8140", "8105"],
                    "Sorcery": ["8224", "8233"],
                    "Shards": ["5008", "5008", "5001"],
                    "Win Rate": "51.72%",
                },
                "rune_2": {
                    "Domination": ["8112", "8139", "8140", "8105"],
                    "Sorcery": ["8226", "8237"],
                    "Shards": ["5008", "5008", "5011"],
                    "Win Rate": "40.00%",
                },
            }
        },
    )
    monkeypatch.setattr(api, "get_champion_slug_by_id", lambda champ_id: "annie")

    page = api.get_recommended_page_for_champion(1)
    assert page is not None
    assert page["primaryStyleId"] == 8100  # Domination (4 perk) = primary
    assert page["subStyleId"] == 8200  # Sorcery (2 perk) = secondary
    # Yüksek winrate'li rune_1 seçilmeli.
    assert page["selectedPerkIds"] == [8112, 8126, 8140, 8105, 8224, 8233, 5008, 5008, 5001]
    assert len(page["selectedPerkIds"]) == 9


def test_recommended_returns_none_for_unknown_slug(monkeypatch):
    monkeypatch.setattr(api, "RUNES_DATA", {})
    monkeypatch.setattr(api, "get_champion_slug_by_id", lambda champ_id: None)
    assert api.get_recommended_page_for_champion(1) is None
