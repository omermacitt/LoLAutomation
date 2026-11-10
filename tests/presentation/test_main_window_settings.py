"""Offscreen window checks with every external operation stubbed."""

import threading

import pytest
from PyQt6.QtWidgets import QSystemTrayIcon

from rune_pilot.domain.user_config import UserConfig
from rune_pilot.domain.game_data import ChampionCatalog, ChampionOption, GameflowStatus
from rune_pilot.presentation import main_window as module
from rune_pilot.presentation.controllers.automation_controller import AutomationController, STATE_STOPPED
from rune_pilot.presentation.controllers.update_controller import UpdateController
from rune_pilot.presentation.api_client import ApiError


def test_desktop_opens_configuration_directly_without_a_login_launcher(qt_app, monkeypatch):
    from unittest.mock import Mock
    app = Mock()
    app.exec.return_value = 0
    window = Mock()
    build_window = Mock(return_value=window)
    monkeypatch.setattr(module, "QApplication", Mock(return_value=app))
    monkeypatch.setattr(module, "MainWindow", build_window)
    with pytest.raises(SystemExit) as stopped:
        module.main()
    assert stopped.value.code == 0
    build_window.assert_called_once()
    window.show.assert_called_once()


class WindowApi:
    def __init__(self):
        self.load_gate = threading.Event()
        self.save_gate = threading.Event()
        self.save_gate.set()
        self.loads = 0
        self.writes = []
        self.fail_next_save = False
        self.catalog_gate = threading.Event()
        self.catalog_gate.set()
        self.catalog_available = True
        self.catalog_calls = 0
        self.phase_gate = threading.Event()
        self.phase_gate.set()
        self.phase = None
        self.phase_calls = 0
        self.catalog = ChampionCatalog(
            all_champions=[ChampionOption(id=266, name="Aatrox"), ChampionOption(id=1, name="Annie")],
            pickable_champions=[ChampionOption(id=266, name="Aatrox"), ChampionOption(id=1, name="Annie")],
        )
        self.config = UserConfig(
            queue_name="Ranked Flex", primary_role_name="Mid", secondary_role_name="Jungle",
            role_champions_ui={"TOP": [266, None, 1]}, role_bans_ui={"TOP": 1},
        )

    def load_settings(self):
        self.loads += 1
        if not self.load_gate.wait(3):
            raise RuntimeError("load gate timed out")
        return self.config.model_copy(deep=True)

    def save_settings(self, config):
        self.writes.append(config.model_copy(deep=True))
        if not self.save_gate.wait(3):
            raise RuntimeError("save gate timed out")
        if self.fail_next_save:
            self.fail_next_save = False
            raise RuntimeError("Could not save settings")
        return config

    def champion_catalog(self):
        self.catalog_calls += 1
        if not self.catalog_gate.wait(3):
            raise ApiError("catalog gate timed out")
        if not self.catalog_available:
            raise ApiError("League Client unavailable")
        return self.catalog

    def gameflow(self):
        self.phase_calls += 1
        self.phase_gate.wait(3)
        return GameflowStatus(phase=self.phase)


@pytest.fixture
def window(qt_app, monkeypatch, request):
    monkeypatch.setattr(module.QMessageBox, "critical", lambda *args: None)
    monkeypatch.setattr(module.MainWindow, "_build_tray_icon", lambda self: setattr(self, "tray_icon", QSystemTrayIcon(self)))
    monkeypatch.setattr(AutomationController, "start_polling", lambda self: None)
    monkeypatch.setattr(UpdateController, "schedule_check", lambda self: None)
    api = WindowApi()
    api.catalog_available = getattr(request, "param", True)
    window = module.MainWindow(api_client=api)
    yield window, api
    api.load_gate.set()
    api.save_gate.set()
    api.catalog_gate.set()
    api.phase_gate.set()
    window._allow_close = True
    window.close()


def test_window_waits_for_settings_and_applies_without_autosaving(window, wait_until):
    view, api = window
    assert not view.tabs.isEnabled()
    assert not view.start_button.isEnabled()
    view._render_automation_state(STATE_STOPPED, "")
    assert not view.start_button.isEnabled()
    view.save_config()
    assert not api.writes
    api.load_gate.set()
    wait_until(lambda: view.settings.ready and not view.champions_query.busy)
    assert view.tabs.isEnabled()
    assert view.start_button.isEnabled()
    assert view.queue_combo.currentText() == "Ranked Flex"
    assert view.primary_role_combo.currentText() == "Mid"
    assert view.role_tabs["TOP"].champion_ids(include_empty=True) == [266, None, 1]
    assert view.role_tabs["TOP"].ban_id == 1
    assert not api.writes


def test_refresh_keeps_local_edits_and_close_waits_for_final_save(window, wait_until):
    view, api = window
    api.load_gate.set()
    wait_until(lambda: view.settings.ready and not view.champions_query.busy)
    view.show()
    view.queue_combo.setCurrentText("Ranked Solo/Duo")
    view.refresh_champions()
    wait_until(lambda: not view.champions_query.busy)
    assert api.loads == 1
    assert view.queue_combo.currentText() == "Ranked Solo/Duo"
    assert view.role_tabs["TOP"].champion_ids(include_empty=True) == [266, None, 1]
    api.save_gate.clear()
    view.close()
    wait_until(lambda: bool(api.writes))
    assert view.isVisible()
    assert not view.centralWidget().isEnabled()
    api.save_gate.set()
    wait_until(lambda: not view.isVisible())
    assert api.writes[-1].queue_name == "Ranked Solo/Duo"


def test_close_before_load_does_not_save_defaults(window):
    view, api = window
    view.close()
    assert not api.writes


def test_failed_close_save_keeps_window_open_for_retry(window, wait_until, monkeypatch):
    view, api = window
    warnings = []
    monkeypatch.setattr(module.QMessageBox, "warning", lambda *args: warnings.append(args))
    api.load_gate.set()
    wait_until(lambda: view.settings.ready and not view.champions_query.busy)
    view.show()
    api.fail_next_save = True
    view.close()
    wait_until(lambda: bool(warnings))
    assert view.isVisible()
    assert view.centralWidget().isEnabled()
    assert not view._closing
    view.close()
    wait_until(lambda: not view.isVisible())
    assert len(api.writes) == 2


@pytest.mark.parametrize("window", [False], indirect=True)
def test_unavailable_champions_do_not_overwrite_saved_selections(window, wait_until):
    view, api = window
    api.load_gate.set()
    wait_until(lambda: view.settings.ready and not view.champions_query.busy)
    assert not view.tabs.isEnabled()
    assert view.refresh_button.isEnabled()
    assert not view.start_button.isEnabled()
    view.save_config()
    view.close()
    assert not api.writes


@pytest.mark.parametrize("window", [False], indirect=True)
def test_champion_recovery_restores_the_loaded_settings(window, wait_until, monkeypatch):
    view, api = window
    api.load_gate.set()
    wait_until(lambda: view.settings.ready and not view.champions_query.busy)
    api.catalog_available = True
    view.refresh_champions()
    wait_until(lambda: not view.champions_query.busy)
    assert api.loads == 1
    assert view.tabs.isEnabled()
    assert view.role_tabs["TOP"].champion_ids(include_empty=True) == [266, None, 1]
    assert view.role_tabs["TOP"].ban_id == 1
    assert not api.writes


def test_refresh_response_keeps_edits_made_while_request_was_running(window, wait_until):
    view, api = window
    api.load_gate.set()
    wait_until(lambda: view.settings.ready and not view.champions_query.busy)
    api.catalog_gate.clear()
    view.refresh_champions()
    view.queue_combo.setCurrentText("Ranked Solo/Duo")
    row = view.role_tabs["TOP"].rows[0]
    row.champion.setCurrentIndex(row.champion.findData(1))
    api.catalog_gate.set()
    wait_until(lambda: not view.champions_query.busy)
    assert view.queue_combo.currentText() == "Ranked Solo/Duo"
    assert row.champion_id == 1


def test_failed_refresh_preserves_existing_selections(window, wait_until):
    view, api = window
    api.load_gate.set()
    wait_until(lambda: view.settings.ready and not view.champions_query.busy)
    api.catalog_available = False
    view.refresh_champions()
    wait_until(lambda: not view.champions_query.busy)
    assert view.role_tabs["TOP"].champion_ids(include_empty=True) == [266, None, 1]
    assert view.tabs.isEnabled()


def test_empty_pick_list_preserves_saved_ids_as_disabled_options(window, wait_until):
    view, api = window
    api.catalog.pickable_champions = []
    api.load_gate.set()
    wait_until(lambda: view.settings.ready and not view.champions_query.busy)
    row = view.role_tabs["TOP"].rows[0]
    assert row.champion_id == 266
    assert not row.champion.model().item(row.champion.currentIndex()).isEnabled()
    assert view._current_config().role_champions_ui["TOP"] == [266, None, 1]


def test_game_started_toast_is_once_across_game_start_and_in_progress(window, wait_until):
    from unittest.mock import Mock
    view, api = window
    view.notifier = Mock()
    view._on_game_phase(GameflowStatus(phase="GameStart"))
    view._on_game_phase(GameflowStatus(phase="InProgress"))
    view._on_game_phase(GameflowStatus(phase=None))
    assert view.notifier.show.call_count == 1


def test_gameflow_poll_does_not_block_or_overlap(window, wait_until):
    from unittest.mock import Mock
    view, api = window
    view.phase_timer.stop()
    view.notifier = Mock()
    api.phase = "GameStart"
    api.phase_gate.clear()
    view.check_game_phase()
    wait_until(lambda: api.phase_calls == 1)
    view.check_game_phase()
    assert api.phase_calls == 1
    assert not view.notifier.show.called
    api.phase_gate.set()
    wait_until(lambda: not view.phase_query.busy)
    assert view.notifier.show.call_count == 1
