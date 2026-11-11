from rune_pilot.domain.user_config import UserConfig
from rune_pilot.presentation.view_models.selection_model import ChampionSelectionModel


def test_qt_role_assignment_save_delete_and_inheritance(qt_app):
    config = UserConfig(
        custom_runes={"106": {"1": {"name": "old"}, "2": {"name": "mid"}}},
        rune_selection={"106": 1},
        role_rune_selection={"MIDDLE": {"106": 2}},
    )
    model = ChampionSelectionModel()
    model.load(config)
    assert model.selected_slot(106, "TOP") == 1
    assert model.selected_slot(106, "MIDDLE") == 2
    model.set_selected_slot(106, 0, "TOP")
    assert model.selected_slot(106, "TOP") == 0
    model.set_selected_slot(106, -1, "TOP")
    assert model.selected_slot(106, "TOP") == 1
    model.save_preset(106, 2, {"name": "shared"}, "TOP")
    model.write_into(config)
    assert config.role_rune_selection == {"MIDDLE": {"106": 2}, "TOP": {"106": 2}}
    assert config.rune_selection == {"106": 1}
    model.delete_preset(106, 2)
    model.write_into(config)
    assert config.role_rune_selection == {"MIDDLE": {"106": 0}, "TOP": {"106": 0}}
    assert config.rune_selection == {"106": 1}


def test_qt_impact_list_includes_missing_preset_references_and_inherited_defaults(qt_app):
    model = ChampionSelectionModel()
    model.load(
        UserConfig(
            rune_selection={"106": 1}, role_rune_selection={"TOP": {"106": 2}, "MIDDLE": {"106": 0}}
        )
    )
    assert model.roles_using_preset(106, 2) == ["TOP"]
    assert set(model.roles_using_preset(106, 1)) == {"JUNGLE", "BOTTOM", "UTILITY"}
