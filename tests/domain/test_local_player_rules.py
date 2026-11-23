"""Local player role/champion and summoner spell resolution."""

from rune_pilot.domain.automation_settings import AutomationSettings
from rune_pilot.domain.champ_select import assigned_role, local_champion, resolve_spells


def spells(config, role, champion):
    return resolve_spells(AutomationSettings.from_mapping(config), role, champion)


def session(**player):
    return {
        "localPlayerCellId": 2,
        "myTeam": ["broken", {"cellId": 1, "championId": 9}, {"cellId": 2, **player}],
    }


def test_assigned_role_is_upper_case_and_empty_when_missing():
    assert assigned_role(session(assignedPosition="middle")) == "MIDDLE"
    assert assigned_role(session(assignedPosition=None)) == ""
    assert assigned_role({}) == ""


def test_local_champion_prefers_lock_then_hover_and_ignores_invalid_ids():
    assert local_champion(session(championId=1, championPickIntent=2)) == 1
    assert local_champion(session(championId=0, championPickIntent=2)) == 2
    assert local_champion(session(championId="x", championPickIntent=-3)) == 0
    assert local_champion({}) == 0


def test_champion_spells_override_per_slot_then_role_pair_then_global():
    config = {
        "primary_role": "MIDDLE",
        "role_champions": {"MIDDLE": [1, 2]},
        "role_summoner_spells": {"MIDDLE": {"spell1Id": 12, "spell2Id": 4}},
        "custom_summoner_spells": {"MIDDLE": {"1": {"spell1Id": 14}}},
        "primary_summoner_spell": 6,
        "secondary_summoner_spell": 7,
    }
    assert spells(config, "MIDDLE", 1) == (14, 4)
    # A replacement champion inherits neither the role pair nor the generic spells.
    assert spells(config, "MIDDLE", 2) == (None, None)
    without_role_pair = {**config, "role_summoner_spells": {}, "custom_summoner_spells": {}}
    assert spells(without_role_pair, "MIDDLE", 1) == (6, 7)


def test_older_clients_without_pools_use_role_and_generic_spells():
    config = {"primary_summoner_spell": 4, "role_summoner_spells": {"TOP": {"spell2Id": 12}}}
    assert spells(config, "TOP", 0) == (4, 12)
