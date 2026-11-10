"""Skin requests preserve the target champion and update shared role state."""

import threading
from unittest.mock import Mock

import pytest
from PyQt6.QtWidgets import QDialog

from rune_pilot.domain.game_data import SkinOption, SkinOptions
from rune_pilot.presentation.view_models.selection_model import ChampionSelectionModel
from rune_pilot.presentation.views import role_tab as module


class SkinApi:
    def __init__(self):
        self.gate = threading.Event()
        self.started = threading.Event()
        self.calls = []
        self.fail = False

    def skin_options(self, champion_id):
        self.calls.append(champion_id)
        self.started.set()
        self.gate.wait(3)
        if self.fail:
            raise RuntimeError("LCU unavailable")
        return SkinOptions(
            champion_id=champion_id,
            skins=[
                SkinOption(id=266000, name="Default"),
                SkinOption(id=266001, name="Justicar"),
            ],
        )


@pytest.fixture
def tab(qt_app):
    api = SkinApi()
    model = ChampionSelectionModel()
    tab = module.RoleTab("TOP", model, lambda cid: {"BOTTOM"}, api_client=api)
    tab.set_champion_options([(266, "Aatrox"), (1, "Annie")])
    tab.restore(None, [266])
    yield tab, model, api
    api.gate.set()
    tab.shutdown()
    tab.close()


def test_skin_loading_is_async_and_applies_to_matching_roles(tab, monkeypatch, wait_until):
    view, model, api = tab
    dialog = Mock()
    dialog.exec.return_value = QDialog.DialogCode.Accepted
    dialog.get_selected_skin_id.return_value = 266001
    factory = Mock(return_value=dialog)
    monkeypatch.setattr(module, "SkinSelectDialog", factory)
    view.open_skin_dialog(0)
    wait_until(api.started.is_set)
    assert not view.rows[0].skin_button.isEnabled()
    assert not factory.called
    api.gate.set()
    wait_until(lambda: not view._skin_query.busy)
    assert model.skin_for("TOP", 266) == 266001
    assert model.skin_for("BOTTOM", 266) == 266001
    assert view.rows[0].skin_button.isEnabled()
    assert factory.call_args.kwargs["skins"] == [(266000, "Default"), (266001, "Justicar")]


def test_changed_champion_discards_old_skin_response(tab, monkeypatch, wait_until):
    view, model, api = tab
    factory = Mock()
    monkeypatch.setattr(module, "SkinSelectDialog", factory)
    view.open_skin_dialog(0)
    wait_until(api.started.is_set)
    view.rows[0].champion.setCurrentIndex(view.rows[0].champion.findData(1))
    api.gate.set()
    wait_until(lambda: not view._skin_query.busy)
    assert not factory.called
    assert model.skin_for("TOP", 266) is None
    assert model.skin_for("TOP", 1) is None


def test_skin_failure_keeps_saved_skin_and_restores_button(tab, monkeypatch, wait_until):
    view, model, api = tab
    api.fail = True
    model.set_skin(266, 266002, {"TOP"})
    warning = Mock()
    monkeypatch.setattr(module.QMessageBox, "critical", warning)
    view.open_skin_dialog(0)
    api.gate.set()
    wait_until(lambda: not view._skin_query.busy)
    assert warning.called
    assert model.skin_for("TOP", 266) == 266002
    assert view.rows[0].skin_button.isEnabled()
