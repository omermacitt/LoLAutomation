"""RunePilot config-file path helpers."""

from __future__ import annotations

import os

from src.rune_pilot.shared.app_meta import APP_ID, LEGACY_APP_ID


def get_config_file_path(app_id: str) -> str:
    """Returns the path to the user config JSON file."""
    base_dir = os.getenv("APPDATA") or os.path.expanduser("~")
    return os.path.join(base_dir, app_id, "user_config.json")


CONFIG_FILE = get_config_file_path(APP_ID)
LEGACY_APP_CONFIG_FILE = get_config_file_path(LEGACY_APP_ID)
