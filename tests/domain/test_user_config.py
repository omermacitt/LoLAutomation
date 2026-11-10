"""Config parsing and legacy migration.

These cases are the reason the migration was moved out of the main window: they cover
config files written by older builds, which used to be untestable because the logic
only ran while a QMainWindow was constructing itself.
"""

from __future__ import annotations

from rune_pilot.domain.user_config import OWNED_KEYS, UserConfig

FLASH = 4
IGNITE = 14
TELEPORT = 12


class TestGarbageInput:
    def test_none_gives_defaults(self):
        config = UserConfig.from_raw(None)
        assert config.custom_runes == {}
        assert config.rune_selection == {}
        assert config.queue_name is None

    def test_non_dict_values_are_dropped_not_raised(self):
        config = UserConfig.from_raw(
            {
                "custom_runes": "not a dict",
                "rune_selection": 42,
                "custom_skins": [1, 2, 3],
                "role_champions_ui": "nope",
            }
        )
        assert config.custom_runes == {}
        assert config.rune_selection == {}
        assert config.custom_skins == {}
        assert config.role_champions_ui == {}

    def test_unknown_roles_and_ids_are_dropped(self):
        config = UserConfig.from_raw(
            {
                "role_bans_ui": {"TOP": 266, "NOT_A_ROLE": 1},
                "custom_runes": {"abc": {"1": {}}, "-5": {"1": {}}},
            }
        )
        assert config.role_bans_ui == {"TOP": 266}
        assert config.custom_runes == {}


class TestRuneMigration:
    def test_legacy_role_keyed_runes_become_champion_keyed(self):
        config = UserConfig.from_raw({"custom_runes": {"TOP": {"266": {"name": "old"}}}})
        assert config.custom_runes == {"266": {"1": {"name": "old"}}}

    def test_legacy_pages_are_selected_so_behaviour_is_preserved(self):
        # Legacy pages were always applied, so the migration must not silently switch
        # the champion back to the recommended page.
        config = UserConfig.from_raw({"custom_runes": {"MIDDLE": {"103": {"name": "old"}}}})
        assert config.rune_selection == {"103": 1}

    def test_explicit_selection_wins_over_the_legacy_default(self):
        config = UserConfig.from_raw(
            {"custom_runes": {"TOP": {"266": {"name": "old"}}}, "rune_selection": {}}
        )
        assert config.rune_selection == {}

    def test_modern_format_is_kept_and_cleaned(self):
        config = UserConfig.from_raw(
            {"custom_runes": {"266": {"1": {"name": "a"}, "7": {"name": "bad slot"}}}}
        )
        assert config.custom_runes == {"266": {"1": {"name": "a"}}}

    def test_selection_pointing_at_a_missing_preset_is_dropped(self):
        config = UserConfig.from_raw(
            {"custom_runes": {"266": {"1": {}}}, "rune_selection": {"266": 3, "99": 1}}
        )
        assert config.rune_selection == {}


class TestSpellMigration:
    def test_global_legacy_spells_apply_to_picked_champions(self):
        config = UserConfig.from_raw(
            {
                "spell1_name": "Flash",
                "spell2_name": "Teleport",
                "role_champions_ui": {"TOP": [266, None, None]},
            }
        )
        assert config.custom_summoner_spells == {
            "TOP": {"266": {"spell1Id": FLASH, "spell2Id": TELEPORT}}
        }

    def test_per_role_legacy_spells_win_over_the_global_pair(self):
        config = UserConfig.from_raw(
            {
                "spell1_name": "Flash",
                "spell2_name": "Teleport",
                "role_spells_ui": {"TOP": {"spell1_name": "Flash", "spell2_name": "Ignite"}},
                "role_champions_ui": {"TOP": [266, None, None]},
            }
        )
        assert config.custom_summoner_spells["TOP"]["266"] == {
            "spell1Id": FLASH,
            "spell2Id": IGNITE,
        }

    def test_existing_per_champion_spells_are_not_overwritten(self):
        config = UserConfig.from_raw(
            {
                "spell1_name": "Flash",
                "spell2_name": "Teleport",
                "custom_summoner_spells": {"TOP": {"266": {"spell1Id": 11, "spell2Id": 3}}},
                "role_champions_ui": {"TOP": [266, None, None]},
            }
        )
        assert config.custom_summoner_spells["TOP"]["266"] == {"spell1Id": 11, "spell2Id": 3}

    def test_spells_stored_by_name_or_as_a_list_are_normalized_to_ids(self):
        config = UserConfig.from_raw(
            {
                "custom_summoner_spells": {
                    "TOP": {"266": {"spell1": "Flash", "spell2": "Ignite"}},
                    "JUNGLE": {"64": ["Flash", 11]},
                }
            }
        )
        assert config.custom_summoner_spells["TOP"]["266"] == {
            "spell1Id": FLASH,
            "spell2Id": IGNITE,
        }
        assert config.custom_summoner_spells["JUNGLE"]["64"] == {"spell1Id": FLASH, "spell2Id": 11}

    def test_nothing_is_migrated_when_the_role_has_no_picks(self):
        config = UserConfig.from_raw({"spell1_name": "Flash", "spell2_name": "Teleport"})
        assert config.custom_summoner_spells == {}


class TestRoundTrip:
    def test_to_raw_exposes_exactly_the_owned_keys(self):
        assert set(UserConfig().to_raw()) == set(OWNED_KEYS)

    def test_reparsing_a_saved_config_is_stable(self):
        original = UserConfig.from_raw(
            {
                "queue_name": "Ranked Flex",
                "primary_role_name": "Mid",
                "role_champions_ui": {"MIDDLE": [103, None, None]},
                "role_bans_ui": {"MIDDLE": 99},
                "custom_runes": {"103": {"1": {"name": "page"}}},
                "rune_selection": {"103": 1},
                "custom_skins": {"MIDDLE": {"103": 103001}},
                "custom_summoner_spells": {
                    "MIDDLE": {"103": {"spell1Id": FLASH, "spell2Id": IGNITE}}
                },
            }
        )
        assert UserConfig.from_raw(original.to_raw()) == original
