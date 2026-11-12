"""Champion availability and recommendation decisions remain independent of I/O."""

import pytest

from rune_pilot.domain.champ_select import extract_spell_pair, is_teammate_showing, pick_candidates
from rune_pilot.domain.champion_service import (
    DuplicateChampionChoices,
    ensure_unique_role_champions,
    is_mode_champion_variant,
    unique_champion_slots,
)
from rune_pilot.domain.constants import MAX_RUNE_PAGE_NAME_LEN
from rune_pilot.domain.rune_rules import build_rune_page_name


def test_duplicate_migration_keeps_slots_and_uniqueness_is_scoped_to_each_role():
    assert unique_champion_slots([266, 266, 103, None, None, 103]) == [
        266,
        None,
        103,
        None,
        None,
        None,
    ]
    ensure_unique_role_champions({"TOP": [266, None, None], "MIDDLE": [266]})
    with pytest.raises(DuplicateChampionChoices):
        ensure_unique_role_champions({"TOP": [266, 103, 266]})


@pytest.mark.parametrize(
    "champion,variant",
    [
        ({"id": 60266, "alias": "Jade_Aatrox", "name": "Aatrox"}, True),
        ({"id": 266, "alias": "Aatrox", "name": "Aatrox"}, False),
        ({"id": 70000, "alias": "FutureChampion", "name": "Aatrox"}, False),
        ({"id": 266, "name": "Aatrox"}, False),
    ],
)
def test_mode_variants_are_identified_by_metadata_not_names_or_id_ranges(champion, variant):
    assert is_mode_champion_variant(champion) is variant


def test_candidates_preserve_preference_order_and_filter_both_teams():
    session = {
        "bans": {"myTeamBans": [1], "theirTeamBans": ["2"]},
        "myTeam": [{"championId": 3}],
        "theirTeam": [{"championId": "4"}],
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


@pytest.mark.parametrize(
    "entry,expected",
    [
        ({"spell1Id": None}, (True, None, False, None)),
        ({"spell1": "4", "spell2": "12"}, (True, 4, True, 12)),
        (["4", "14"], (True, 4, True, 14)),
        (None, (False, None, False, None)),
    ],
)
def test_spell_pair_distinguishes_missing_from_explicitly_disabled(entry, expected):
    assert extract_spell_pair(entry) == expected


@pytest.mark.parametrize(
    "prefix,name",
    [
        ("Auto", "Nunu & Willump"),
        ("Custom 3", "VeryLongChampionName"),
        ("x" * 80, "Annie"),
        ("", ""),
    ],
)
def test_page_name_fits_client_limit(prefix, name):
    result = build_rune_page_name(prefix=prefix, champion_name=name)
    assert 0 < len(result) <= MAX_RUNE_PAGE_NAME_LEN
