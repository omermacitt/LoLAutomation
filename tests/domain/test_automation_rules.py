"""Champion availability and recommendation decisions remain independent of I/O."""

import pytest

from rune_pilot.domain.champ_select import extract_spell_pair, pick_candidates, is_teammate_showing
from rune_pilot.domain.constants import MAX_RUNE_PAGE_NAME_LEN
from rune_pilot.domain.champion_service import is_mode_champion_variant
from rune_pilot.domain.champion_service import DuplicateChampionChoices, ensure_unique_role_champions, unique_champion_slots
from rune_pilot.domain.rune_rules import build_rune_page_name, recommended_page


def test_duplicate_migration_keeps_slots_and_uniqueness_is_scoped_to_each_role():
    assert unique_champion_slots([266, 266, 103, None, None, 103]) == [266, None, 103, None, None, None]
    ensure_unique_role_champions({"TOP": [266, None, None], "MIDDLE": [266]})
    with pytest.raises(DuplicateChampionChoices):
        ensure_unique_role_champions({"TOP": [266, 103, 266]})


@pytest.mark.parametrize("champion,variant", [
    ({"id": 60266, "alias": "Jade_Aatrox", "name": "Aatrox"}, True),
    ({"id": 266, "alias": "Aatrox", "name": "Aatrox"}, False),
    ({"id": 70000, "alias": "FutureChampion", "name": "Aatrox"}, False),
    ({"id": 266, "name": "Aatrox"}, False),
])
def test_mode_variants_are_identified_by_metadata_not_names_or_id_ranges(champion, variant):
    assert is_mode_champion_variant(champion) is variant


def test_candidates_preserve_preference_order_and_filter_both_teams():
    session = {
        "bans": {"myTeamBans": [1], "theirTeamBans": ["2"]},
        "myTeam": [{"championId": 3}], "theirTeam": [{"championId": "4"}],
    }
    preferences = [None, "bad", -1, 1, 2, 3, 4, "7", 5, 6]
    assert pick_candidates(session, preferences, {1, 2, 3, 4, 5, 7}) == [7, 5]
    assert pick_candidates(session, preferences, None) == [7, 5, 6]
    assert pick_candidates(session, preferences, set()) == []


def test_teammate_hover_protects_ban_but_does_not_count_as_a_pick():
    session = {"myTeam": [{"championId": 0, "championPickIntent": "1"}]}
    assert is_teammate_showing(session, 1)
    assert not is_teammate_showing(session, 0)
    assert pick_candidates(session, [1], None) == [1]


@pytest.mark.parametrize("entry,expected", [
    ({"spell1Id": None}, (True, None, False, None)),
    ({"spell1": "4", "spell2": "12"}, (True, 4, True, 12)),
    (["4", "14"], (True, 4, True, 14)),
    (None, (False, None, False, None)),
])
def test_spell_pair_distinguishes_missing_from_explicitly_disabled(entry, expected):
    assert extract_spell_pair(entry) == expected


def test_direct_rune_format_normalizes_ids_and_requires_nine_perks():
    raw = {"primaryStyleId": "8000", "subStyleId": "8100", "selectedPerkIds": list(map(str, range(1, 10)))}
    page = recommended_page(1, {"1": raw}, None)
    assert page == {"primaryStyleId": 8000, "subStyleId": 8100, "selectedPerkIds": list(range(1, 10))}
    assert raw["primaryStyleId"] == "8000"
    raw["selectedPerkIds"].pop()
    assert recommended_page(1, {"1": raw}, None) is None


def test_legacy_runes_choose_highest_valid_winrate_and_fall_back():
    low = {"Domination": [1, 2, 3, 4], "Sorcery": [5, 6], "Shards": [7, 8, 9], "Win Rate": "51.2%"}
    high = {**low, "Domination": [11, 12, 13, 14], "Win Rate": "55,8%"}
    data = {"annie": {"rune_1": low, "rune_2": high, "rune_3": {"Win Rate": "90%"}}}
    assert recommended_page(1, data, "annie")["selectedPerkIds"][:4] == [11, 12, 13, 14]
    high["Shards"] = []
    assert recommended_page(1, data, "annie")["selectedPerkIds"] == list(range(1, 10))
    assert recommended_page(1, data, None) is None


@pytest.mark.parametrize("prefix,name", [("Auto", "Nunu & Willump"), ("Custom 3", "VeryLongChampionName"), ("x" * 80, "Annie"), ("", "")])
def test_page_name_fits_client_limit(prefix, name):
    result = build_rune_page_name(prefix=prefix, champion_name=name)
    assert 0 < len(result) <= MAX_RUNE_PAGE_NAME_LEN
