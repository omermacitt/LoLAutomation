"""Shared catalog loading and late icon decoration preserve all preset choices."""

import threading

import pytest
from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtGui import QColor, QPixmap

from rune_pilot.domain.game_data import RuneCatalog
from rune_pilot.presentation.dialogs.rune_presets_dialog import RunePresetsDialog
from rune_pilot.presentation.dialogs.runes_dialog import RunePageDialog


def rune_catalog():
    styles = []
    for sid, name in [(8000, "Precision"), (8100, "Domination")]:
        slots = [{"runes": [sid + i * 10 + 1, sid + i * 10 + 2]} for i in range(4)]
        styles.append({"id": sid, "name": name, "slots": slots})
    shards = [[5005, 5008], [5008, 5002], [5001, 5003]]
    styles.append({"id": 5000, "name": "StatMods", "slots": [{"runes": row} for row in shards]})
    ids = {pid for style in styles for slot in style["slots"] for pid in slot["runes"]}
    return RuneCatalog(styles=styles, perks=[{"id": pid, "name": str(pid)} for pid in ids])


class RuneApi:
    def __init__(self, icon):
        self.catalog_gate = threading.Event()
        self.icon_gate = threading.Event()
        self.loads = 0
        self.icon_calls = []
        self.icon_bytes = icon
        self.fail_load = False

    def rune_catalog(self):
        self.loads += 1
        self.catalog_gate.wait(3)
        if self.fail_load:
            raise RuntimeError("Could not load runes")
        return rune_catalog()

    def perk_icon(self, perk_id):
        self.icon_calls.append(perk_id)
        self.icon_gate.wait(3)
        return self.icon_bytes


@pytest.fixture
def rune_api(qt_app):
    pixmap = QPixmap(2, 2)
    pixmap.fill(QColor("red"))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert pixmap.save(buffer, "PNG")
    api = RuneApi(bytes(buffer.data()))
    yield api
    api.catalog_gate.set()
    api.icon_gate.set()


def test_presets_load_one_catalog_restore_pages_and_keep_edits_during_icons(rune_api, wait_until):
    original = {
        "name": "Saved",
        "primaryStyleId": 8000,
        "subStyleId": 8100,
        "selectedPerkIds": [8002, 8012, 8022, 8032, 8111, 8121, 5008, 5002, 5003],
    }
    saved = []
    dialog = RunePresetsDialog(
        champion_id=266,
        champion_name="Aatrox",
        existing_presets={"1": original},
        on_save_preset=lambda slot, page: saved.append((slot, page)),
        on_delete_preset=lambda slot: None,
        api_client=rune_api,
    )
    try:
        assert not dialog.save_btn.isEnabled()
        assert all(
            not editor.primary_style_combo.isEnabled() for editor in dialog._editors.values()
        )
        rune_api.catalog_gate.set()
        wait_until(lambda: dialog.save_btn.isEnabled())
        assert rune_api.loads == 1
        editor = dialog._editors[1]
        assert editor.get_rune_page(allow_incomplete=True) == original
        editor.primary_rune_combos[0].setCurrentIndex(0)
        editor.name_edit.setText("Edited while icons load")
        edited = editor.get_rune_page(allow_incomplete=True)
        assert edited is not None
        rune_api.icon_gate.set()
        wait_until(lambda: not dialog.rune_data._queue and not dialog.rune_data._icon_query.busy)
        assert editor.get_rune_page(allow_incomplete=True) == edited
        assert not editor.primary_rune_combos[0].itemIcon(0).isNull()
        assert len(rune_api.icon_calls) == len(set(rune_api.icon_calls))
        dialog._save_current()
        assert saved == [(1, edited)]
    finally:
        rune_api.catalog_gate.set()
        rune_api.icon_gate.set()
        dialog.close()


def test_failed_catalog_keeps_editor_disabled_and_can_be_retried(rune_api, wait_until):
    rune_api.fail_load = True
    dialog = RunePageDialog(champion_name="Aatrox", api_client=rune_api)
    try:
        rune_api.catalog_gate.set()
        wait_until(lambda: not dialog.rune_data._catalog_query.busy)
        assert not dialog._data_ready
        assert not dialog._save_button.isEnabled()
        assert not dialog.retry_button.isHidden()
        rune_api.fail_load = False
        dialog._retry_load()
        wait_until(lambda: dialog._data_ready)
        assert dialog._save_button.isEnabled()
        assert rune_api.loads == 2
    finally:
        rune_api.icon_gate.set()
        dialog.close()
