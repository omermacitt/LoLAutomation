import json

import pytest

from rune_pilot.application.config_service import ConfigConflict, ConfigService
from rune_pilot.domain.models import AutomationConfig
from rune_pilot.domain.rune_selection import resolve_rune_choice
from rune_pilot.domain.user_config import UserConfig
from rune_pilot.infrastructure.config_repository import ConfigRepository


@pytest.mark.parametrize(
    "value, expected", [(0, 0), (1, 1), (3, 3), (None, 0), (False, 0), ("2", 0), (4, 0)]
)
def test_explicit_assignments_never_become_missing(value, expected):
    raw = {"role_rune_selection": {"TOP": {"106": value}, "MIDDLE": {"106": 2}, "bad": {"106": 1}}}
    config = UserConfig.from_raw(raw)
    assert config.role_rune_selection == {"TOP": {"106": expected}, "MIDDLE": {"106": 2}}
    assert AutomationConfig(**raw).role_rune_selection == config.role_rune_selection
    assert UserConfig(**raw).role_rune_selection == config.role_rune_selection
    assert UserConfig.from_raw(config.to_raw()) == config


def test_absence_and_zero_and_dangling_reference_resolve_differently():
    raw = {
        "custom_runes": {"106": {"1": {}, "2": {}}},
        "rune_selection": {"106": 1},
        "role_rune_selection": {"TOP": {"106": 0}, "MIDDLE": {"106": 2}, "JUNGLE": {"106": 3}},
    }
    assert resolve_rune_choice(raw, "TOP", 106).slot == 0
    assert resolve_rune_choice(raw, "MIDDLE", 106).slot == 2
    assert resolve_rune_choice(raw, "BOTTOM", 106).slot == 1
    assert resolve_rune_choice(raw, "", 106).slot == 1
    assert resolve_rune_choice(raw, "JUNGLE", 106).missing
    assert resolve_rune_choice(raw, "JUNGLE", 106).slot == 0
    assert UserConfig.from_raw(raw).role_rune_selection["JUNGLE"]["106"] == 3


def test_role_settings_round_trip_revision_and_foreign_fields(tmp_path):
    path = tmp_path / "config.json"
    raw = {
        "theme": "keep",
        "custom_runes": {"106": {"1": {"name": "old"}}},
        "rune_selection": {"106": 1},
    }
    path.write_text(json.dumps(raw), encoding="utf-8")
    service = ConfigService(ConfigRepository(str(path), fallback_paths=()))
    config = service.load()
    assert config.role_rune_selection == {}
    assert json.loads(path.read_text()) == raw  # Read never migrates the file in place.
    revision = service.revision(config)
    config.role_rune_selection = {"TOP": {"106": 0}, "MIDDLE": {"106": 2}}
    assert service.save(config, expected_revision=revision)
    loaded = service.load()
    assert loaded == config
    assert service.revision(loaded) != revision
    assert json.loads(path.read_text())["theme"] == "keep"
    with pytest.raises(ConfigConflict):
        service.save(UserConfig(), expected_revision=revision)
