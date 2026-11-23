"""Settings snapshots keep the worker's historical tolerance for partial dictionaries."""

from rune_pilot.domain.automation_settings import AutomationSettings


def test_partial_snapshot_does_not_take_http_defaults():
    settings = AutomationSettings.from_mapping({})
    assert settings.queue_id is None
    assert settings.auto_queue is True
    assert settings.recommendations_enabled is True
    assert settings.primary_role == ""
    assert settings.role_champions == {}


def test_roles_queue_and_spells_are_normalized_once():
    settings = AutomationSettings.from_mapping(
        {
            "primary_role": "middle",
            "secondary_role": None,
            "queue_id": "420",
            "auto_queue": None,
            "primary_summoner_spell": "4",
            "secondary_summoner_spell": 0,
        }
    )
    assert (settings.primary_role, settings.secondary_role) == ("MIDDLE", "")
    assert settings.queue_id == 420
    assert settings.auto_queue is False
    # Rune recommendations historically compare the raw queue value.
    assert settings.recommendations_enabled is False
    assert (settings.primary_spell, settings.secondary_spell) == (4, None)
    assert AutomationSettings.from_mapping({"queue_id": "x"}).queue_id is None
    assert not AutomationSettings.from_mapping({"queue_id": 450}).recommendations_enabled


def test_bans_and_pools_fall_back_to_primary_role_only_without_assigned_position():
    settings = AutomationSettings.from_mapping(
        {
            "primary_role": "TOP",
            "role_bans": {"TOP": "5", "JUNGLE": 0},
            "role_champions": {"TOP": [1, None], "JUNGLE": "bad"},
        }
    )
    assert settings.ban_for("") == 5
    assert settings.ban_for("JUNGLE") is None
    assert settings.preferences_for("") == (1, None)
    assert settings.preferences_for("JUNGLE") == ()
    assert settings.effective_role("") == "TOP"
    assert settings.effective_role("BOTTOM") == "BOTTOM"


def test_champion_entries_prefer_string_keys_over_legacy_integer_keys():
    settings = AutomationSettings.from_mapping(
        {
            "custom_skins": {"TOP": {1: 1001, "1": 1002, 2: 2003, "3": None, 3: 3004}},
            "custom_summoner_spells": {"TOP": "bad", "MIDDLE": {4: {"spell1Id": 4}}},
        }
    )
    assert settings.champion_skin("TOP", 1) == 1002
    assert settings.champion_skin("TOP", 2) == 2003
    assert settings.champion_skin("TOP", 3) == 3004
    assert settings.champion_skin("MIDDLE", 1) is None
    assert settings.champion_spell_entry("MIDDLE", 4) == {"spell1Id": 4}
    assert settings.champion_spell_entry("TOP", 4) is None


def test_rune_choice_matches_dictionary_resolution():
    raw = {
        "role_rune_selection": {"MIDDLE": {"106": 2}},
        "rune_selection": {"106": 1},
        "custom_runes": {"106": {"1": {"primaryStyleId": 8000}, "2": {"primaryStyleId": 8100}}},
    }
    settings = AutomationSettings.from_mapping(raw)
    assert settings.rune_choice("MIDDLE", 106).slot == 2
    assert settings.rune_choice("TOP", 106).slot == 1
    assert settings.custom_rune_page(106, 2) == {"primaryStyleId": 8100}
    assert settings.custom_rune_page(106, 3) is None
    assert settings.custom_rune_page(7, 1) is None
