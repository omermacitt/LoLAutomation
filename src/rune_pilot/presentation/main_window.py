"""
The RunePilot main window.

Assembles the pieces and owns none of their logic: role tabs render and edit the
shared `ChampionSelectionModel`, `AutomationController` talks to the backend,
`UpdateController` handles releases, and `SettingsController` persists settings. What
stays here is the window chrome, the queue/role preference controls, and the wiring
between those parts.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from PyQt6.QtCore import QEvent, QSize, Qt, QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from rune_pilot.domain.constants import QUEUE_MODES, ROLES
from rune_pilot.domain.game_data import ChampionCatalog, GameflowStatus
from rune_pilot.domain.update import UpdateInfo
from rune_pilot.domain.user_config import UserConfig
from rune_pilot.presentation.api_client import ApiClient
from rune_pilot.presentation.controllers.automation_controller import (
    STATE_CHECKING,
    STATE_OFFLINE,
    STATE_RUNNING,
    STATE_STARTING,
    STATE_STOPPED,
    STATE_STOPPING,
    AutomationController,
)
from rune_pilot.presentation.controllers.background_query import BackgroundQuery
from rune_pilot.presentation.controllers.settings_controller import SettingsController
from rune_pilot.presentation.controllers.update_controller import UpdateController
from rune_pilot.presentation.notifications import DesktopNotifier
from rune_pilot.presentation.styles import STYLESHEET
from rune_pilot.presentation.view_models.selection_model import ChampionSelectionModel
from rune_pilot.presentation.views.role_tab import RoleTab
from rune_pilot.presentation.widgets.combo_utils import (
    set_all_combo_items_enabled,
    set_combo_item_enabled,
)
from rune_pilot.shared.app_meta import APP_DISPLAY_NAME, APP_ID, __version__
from rune_pilot.shared.resource import resource_path

DEFAULT_QUEUE_ID = 420
NONE_ROLE_LABEL = "None"
PHASE_POLL_MS = 2000

ROLE_TABS: tuple[tuple[str, str], ...] = (
    ("Top", "TOP"),
    ("Jungle", "JUNGLE"),
    ("Mid", "MIDDLE"),
    ("ADC", "BOTTOM"),
    ("Support", "UTILITY"),
)


@dataclass(frozen=True)
class _StateVisuals:
    """How one automation state renders across the buttons and the status badges."""

    start_text: str
    start_icon: str
    start_enabled: bool
    stop_text: str
    stop_icon: str
    stop_enabled: bool
    badge: str
    corner: str
    busy: bool


_STATE_VISUALS: dict[str, _StateVisuals] = {
    STATE_RUNNING: _StateVisuals(
        "Running", "running", False, "Stop", "stop", True, "Status: Running", "Running", False
    ),
    STATE_STOPPED: _StateVisuals(
        "Start", "play", True, "Stop", "stop", False, "Status: Stopped", "Stopped", False
    ),
    STATE_OFFLINE: _StateVisuals(
        "Start", "play", True, "Stop", "stop", False, "Status: Server offline", "Offline", False
    ),
    STATE_STARTING: _StateVisuals(
        "Starting…", "wait", False, "Stop", "stop", False, "Status: Starting…", "Starting…", True
    ),
    STATE_STOPPING: _StateVisuals(
        "Running",
        "running",
        False,
        "Stopping…",
        "wait",
        False,
        "Status: Stopping…",
        "Stopping…",
        True,
    ),
    STATE_CHECKING: _StateVisuals(
        "Start", "play", True, "Stop", "stop", False, "Status: Checking…", "Checking…", True
    ),
}


class MainWindow(QMainWindow):
    """RunePilot main window."""

    def __init__(self, api_client: ApiClient | None = None) -> None:
        super().__init__()
        client = api_client if api_client is not None else ApiClient()
        self._client = client
        self.champions_query = BackgroundQuery(self)
        self.phase_query = BackgroundQuery(self)
        self.settings = SettingsController(client, parent=self)
        self._closing = False
        self._allow_close = False
        self._champions_loaded = False
        self._champion_names: dict[int, str] = {}
        self._loaded_config = UserConfig()
        self.model = ChampionSelectionModel(self)
        # Set while a saved config is being applied to the widgets, so the edits we
        # make ourselves are not mistaken for the user's and written straight back.
        self._loading = False

        self.automation = AutomationController(self._build_automation_payload, client, parent=self)
        self.updater = UpdateController(self, api_client=self._client)
        self._update_progress: QProgressDialog | None = None

        self.setWindowTitle(f"{APP_DISPLAY_NAME} – Role-Based Selection")
        self.resize(700, 500)
        try:
            self.setWindowIcon(QIcon(resource_path("assets/app_icon.png")))
        except Exception:
            pass

        self._build_ui()
        self._connect_signals()
        self._on_settings_ready(False)

        self.load_champions()
        self.load_config()

        self._build_tray_icon()
        self._start_phase_monitor()

        self.automation.start_polling()
        self.updater.schedule_check()

    # -- construction --------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addLayout(self._build_corner_status())
        layout.addWidget(_title_label(APP_DISPLAY_NAME, "appTitle"))
        layout.addWidget(
            _title_label("Role-based ban / champion pick & rune automation", "appSubtitle")
        )
        layout.addWidget(self._build_settings_group())

        self.tabs = QTabWidget()
        self.role_tabs: dict[str, RoleTab] = {}
        for display_name, role_key in ROLE_TABS:
            tab = RoleTab(
                role_key,
                self.model,
                self._roles_with_champion,
                parent=self,
                api_client=self._client,
            )
            self.tabs.addTab(tab, display_name)
            self.role_tabs[role_key] = tab
        layout.addWidget(self.tabs)

        layout.addLayout(self._build_action_buttons())

    def _build_corner_status(self) -> QHBoxLayout:
        self.corner_status_label = QLabel("Checking…")
        self.corner_status_label.setObjectName("cornerStatusLabel")
        self.corner_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.corner_status_label.setProperty("state", STATE_CHECKING)
        self.corner_status_label.setToolTip("Automation status")

        self.corner_progress = QProgressBar()
        self.corner_progress.setObjectName("cornerProgress")
        self.corner_progress.setTextVisible(False)
        self.corner_progress.setFixedSize(90, 10)
        self.corner_progress.setRange(0, 0)  # indeterminate until the first health poll
        self.corner_progress.setProperty("state", STATE_CHECKING)

        container = QWidget()
        inner = QHBoxLayout(container)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(6)
        inner.addWidget(self.corner_status_label)
        inner.addWidget(self.corner_progress)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addStretch(1)
        row.addWidget(container, alignment=Qt.AlignmentFlag.AlignRight)
        return row

    def _build_settings_group(self) -> QGroupBox:
        group = QGroupBox("General Settings")
        grid = QGridLayout(group)

        grid.addWidget(QLabel("Game Mode:"), 0, 0)
        self.queue_combo = QComboBox()
        self.queue_combo.addItems(list(QUEUE_MODES))
        self.queue_combo.setCurrentText("Ranked Solo/Duo")
        grid.addWidget(self.queue_combo, 0, 1)

        self.refresh_button = QPushButton("Refresh Champions")
        self.refresh_button.setObjectName("refreshButton")
        self.refresh_button.setFixedHeight(32)
        grid.addWidget(self.refresh_button, 0, 2, 1, 2)

        self.settings_status = QLabel("Loading saved settings…")
        grid.addWidget(self.settings_status, 2, 0, 1, 4)
        self.champion_status = QLabel("Loading champions…")
        grid.addWidget(self.champion_status, 3, 0, 1, 4)

        grid.addWidget(QLabel("1st Preference:"), 1, 0)
        self.primary_role_combo = QComboBox()
        grid.addWidget(self.primary_role_combo, 1, 1)

        grid.addWidget(QLabel("2nd Preference:"), 1, 2)
        self.secondary_role_combo = QComboBox()
        grid.addWidget(self.secondary_role_combo, 1, 3)

        for combo in (self.primary_role_combo, self.secondary_role_combo):
            combo.addItems(list(ROLES))
        self.primary_role_combo.setCurrentText("Top")
        self.secondary_role_combo.setCurrentText("Jungle")

        self._updating_role_preferences = False
        self._refresh_role_preference_exclusion()
        return group

    def _build_action_buttons(self) -> QHBoxLayout:
        style = self.style()
        self._icons = {
            "play": style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay),
            "stop": style.standardIcon(QStyle.StandardPixmap.SP_MediaStop),
            "running": style.standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton),
            "wait": style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload),
        }

        self.start_button = QPushButton("Start")
        self.start_button.setObjectName("startButton")
        self.start_button.setToolTip("Start automation")
        self.start_button.setFixedHeight(40)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setToolTip("Stop automation")
        self.stop_button.setFixedHeight(40)
        self.stop_button.setEnabled(False)

        for button in (self.start_button, self.stop_button):
            button.setIconSize(QSize(18, 18))
            button.setProperty("automationState", STATE_STOPPED)

        self.automation_status = QLabel("Status: Checking…")
        self.automation_status.setObjectName("automationStatus")
        self.automation_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.automation_status.setFixedHeight(32)
        self.automation_status.setProperty("state", STATE_CHECKING)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(self.start_button)
        row.addWidget(self.stop_button)
        row.addStretch(1)
        row.addWidget(self.automation_status)
        return row

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(self.start_automation)
        self.stop_button.clicked.connect(self.automation.request_stop)
        self.refresh_button.clicked.connect(self.refresh_champions)
        self.queue_combo.currentIndexChanged.connect(self._on_settings_edited)

        self.primary_role_combo.currentIndexChanged.connect(
            lambda _=0: self._on_role_preference_changed("primary")
        )
        self.secondary_role_combo.currentIndexChanged.connect(
            lambda _=0: self._on_role_preference_changed("secondary")
        )

        for tab in self.role_tabs.values():
            tab.champion_changed.connect(self._refresh_tabs)
            tab.champion_changed.connect(self._on_settings_edited)
            tab.ban_combo.currentIndexChanged.connect(self._on_settings_edited)

        self.model.changed.connect(self._on_model_changed)

        self.settings.loaded.connect(self._apply_config)
        self.settings.ready_changed.connect(self._on_settings_ready)
        self.settings.failed.connect(self._on_settings_failed)
        self.settings.saved.connect(self._on_settings_saved)
        self.champions_query.succeeded.connect(self._on_champions_loaded)
        self.champions_query.failed.connect(self._on_champions_failed)
        self.champions_query.finished.connect(
            lambda: self.refresh_button.setEnabled(self.settings.ready and not self._closing)
        )
        self.phase_query.succeeded.connect(self._on_game_phase)

        self.automation.state_changed.connect(self._render_automation_state)
        self.automation.notified.connect(self._show_notification)

        self.updater.update_available.connect(self._on_update_available)
        self.updater.download_started.connect(self._show_download_progress)
        self.updater.download_finished.connect(self._on_download_finished)

    def _build_tray_icon(self) -> None:
        self.notifier = DesktopNotifier()
        self.tray_icon = QSystemTrayIcon(self)

        icon_path = resource_path("assets/app_icon.png")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

        menu = QMenu(self)
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.showNormal)
        menu.addAction(show_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _start_phase_monitor(self) -> None:
        self.last_phase: str | None = None
        self.phase_timer = QTimer(self)
        self.phase_timer.timeout.connect(self.check_game_phase)
        self.phase_timer.start(PHASE_POLL_MS)

    # -- role preferences ----------------------------------------------------

    def _refresh_role_preference_exclusion(self) -> None:
        """Keeps the same role from being both first and second preference."""
        for combo in (self.primary_role_combo, self.secondary_role_combo):
            set_all_combo_items_enabled(combo)

        for source, target in (
            (self.primary_role_combo, self.secondary_role_combo),
            (self.secondary_role_combo, self.primary_role_combo),
        ):
            name = source.currentText()
            if name == NONE_ROLE_LABEL:
                continue
            index = target.findText(name)
            if index >= 0:
                set_combo_item_enabled(target, index, False)

    def _on_role_preference_changed(self, changed: str) -> None:
        if self._updating_role_preferences:
            return

        self._updating_role_preferences = True
        try:
            primary = self.primary_role_combo.currentText()
            secondary = self.secondary_role_combo.currentText()
            if primary != NONE_ROLE_LABEL and primary == secondary:
                # Clear whichever one the user did not just touch.
                other = (
                    self.secondary_role_combo if changed == "primary" else self.primary_role_combo
                )
                other.setCurrentText(NONE_ROLE_LABEL)
            self._refresh_role_preference_exclusion()
        finally:
            self._updating_role_preferences = False
        self._on_settings_edited()

    # -- champions -----------------------------------------------------------

    def refresh_champions(self) -> None:
        if not self.settings.ready:
            return
        self.load_champions()

    def load_champions(self) -> None:
        if self.champions_query.run(self._client.champion_catalog):
            self.refresh_button.setEnabled(False)
            self.champion_status.setText("Loading champions…")

    def _on_champions_loaded(self, catalog: ChampionCatalog) -> None:
        if self._closing:
            return
        # Take the latest edits when the response arrives, not when refresh starts.
        config = (
            self._current_config()
            if self._champions_loaded and self.settings.ready
            else self._loaded_config
        )
        self._champion_names = {item.id: item.name for item in catalog.all_champions}
        ban_entries = [(item.id, item.name) for item in catalog.all_champions]
        pick_entries = [(item.id, item.name) for item in catalog.pickable_champions]
        self._loading = True
        try:
            for tab in self.role_tabs.values():
                tab.set_ban_options(ban_entries)
                tab.set_champion_options(pick_entries)
            self._champions_loaded = True
            self._apply_config(config)
        finally:
            self._loading = False
        self.champion_status.setText("Champions loaded")
        self.champion_status.setToolTip("")
        self._on_settings_ready(self.settings.ready)

    def _on_champions_failed(self, error: str) -> None:
        self.champion_status.setText("Could not load champions; use Refresh Champions to retry")
        self.champion_status.setToolTip(error)

    def _roles_with_champion(self, champ_id: int) -> set[str]:
        return {role_key for role_key, tab in self.role_tabs.items() if tab.has_champion(champ_id)}

    def _refresh_tabs(self) -> None:
        for tab in self.role_tabs.values():
            tab.refresh()

    # -- config --------------------------------------------------------------

    def load_config(self) -> None:
        self.settings.load()

    def _apply_config(self, config: UserConfig) -> None:
        self._loaded_config = config.model_copy(deep=True)
        was_loading = self._loading
        self._loading = True
        try:
            if config.queue_name:
                self.queue_combo.setCurrentText(config.queue_name)
            if config.primary_role_name:
                self.primary_role_combo.setCurrentText(config.primary_role_name)
            if config.secondary_role_name:
                self.secondary_role_combo.setCurrentText(config.secondary_role_name)

            self.model.load(config)

            for role_key, tab in self.role_tabs.items():
                # Settings and champion responses can arrive in either order.
                if self._champions_loaded:
                    ban = config.role_bans_ui.get(role_key)
                    if ban is not None and tab.ban_combo.findData(ban) < 0:
                        tab.ban_combo.addItem(f"{ban} (Unavailable)", ban)
                        set_combo_item_enabled(tab.ban_combo, tab.ban_combo.findData(ban), False)
                    for row, cid in zip(
                        tab.rows, config.role_champions_ui.get(role_key, []), strict=False
                    ):
                        if cid is not None and row.champion.findData(cid) < 0:
                            row.champion.addItem(
                                f"{self._champion_names.get(cid, str(cid))} (Unavailable)", cid
                            )
                            set_combo_item_enabled(row.champion, row.champion.findData(cid), False)
                tab.restore(
                    config.role_bans_ui.get(role_key),
                    config.role_champions_ui.get(role_key, []),
                )
            self._refresh_tabs()
        finally:
            self._loading = was_loading

    def save_config(self) -> None:
        if self._loading or not self.settings.ready or not self._champions_loaded:
            return
        self.settings.save(self._current_config())

    def _on_settings_edited(self, _index: int = 0) -> None:
        if self._loading or not self.settings.ready:
            return
        self.save_config()
        self.automation.schedule_config_push()

    def _on_settings_ready(self, ready: bool) -> None:
        editable = ready and self._champions_loaded
        self.tabs.setEnabled(editable)
        for widget in (
            self.queue_combo,
            self.primary_role_combo,
            self.secondary_role_combo,
        ):
            widget.setEnabled(editable)
        self.refresh_button.setEnabled(ready and not self.champions_query.busy)
        self.settings_status.setText(
            "Settings loaded"
            if editable
            else "Refresh champions to edit saved settings" if ready else "Loading saved settings…"
        )
        self.settings_status.setToolTip("")
        self.start_button.setEnabled(
            editable
            and self.automation.state
            not in (
                STATE_RUNNING,
                STATE_STARTING,
                STATE_STOPPING,
            )
        )

    def _on_settings_failed(self, error: str) -> None:
        self.settings_status.setText(
            "Settings save failed; retrying…"
            if self.settings.ready
            else "Waiting for backend to load saved settings…"
        )
        self.settings_status.setToolTip(error)
        if self._closing:
            self._closing = False
            self.centralWidget().setEnabled(True)
            QMessageBox.warning(
                self, "Settings", f"Could not save settings. Please retry closing.\n\n{error}"
            )

    def _on_settings_saved(self) -> None:
        self.settings_status.setText("Settings saved")
        self.settings_status.setToolTip("")
        if self._closing:
            self._allow_close = True
            self.close()

    def _current_config(self) -> UserConfig:
        """The window's current state as a `UserConfig`."""
        for tab in self.role_tabs.values():
            tab.sync_spells_into_model()

        config = UserConfig(
            queue_name=self.queue_combo.currentText(),
            primary_role_name=self.primary_role_combo.currentText(),
            secondary_role_name=self.secondary_role_combo.currentText(),
            role_champions_ui={
                role_key: tab.champion_ids(include_empty=True)
                for role_key, tab in self.role_tabs.items()
            },
            role_bans_ui={role_key: tab.ban_id for role_key, tab in self.role_tabs.items()},
        )
        self.model.write_into(config)
        return config

    def _on_model_changed(self) -> None:
        """A rune, skin or spell edit: re-render every tab, persist, push if running."""
        if self._loading:
            return
        self._refresh_tabs()
        self.save_config()
        self.automation.schedule_config_push()

    # -- automation ----------------------------------------------------------

    def start_automation(self) -> None:
        if not self.settings.ready or not self._champions_loaded or self._closing:
            return
        missing = self._missing_selections()
        if missing:
            QMessageBox.warning(
                self,
                "Missing Selection",
                "You must select a ban and at least 1 champion for all roles before "
                f"starting {APP_DISPLAY_NAME}:\n\n" + "\n".join(missing),
            )
            return

        self.save_config()
        self.automation.request_start()

    def _missing_selections(self) -> list[str]:
        role_display = {role_key: name for name, role_key in ROLES.items() if role_key}

        missing: list[str] = []
        for role_key, tab in self.role_tabs.items():
            display = role_display.get(role_key, role_key)
            has_ban = tab.ban_id is not None
            has_champion = bool(tab.champion_ids())

            if not has_ban and not has_champion:
                missing.append(f"- {display}: ban and champion not selected")
            elif not has_ban:
                missing.append(f"- {display}: ban not selected")
            elif not has_champion:
                missing.append(f"- {display}: at least 1 champion not selected")
        return missing

    def _build_automation_payload(self) -> dict:
        config = self._current_config()

        primary_role = ROLES.get(self.primary_role_combo.currentText())
        secondary_role = ROLES.get(self.secondary_role_combo.currentText())

        role_summoner_spells: dict[str, dict[str, int | None]] = {}
        role_champions: dict[str, list[int]] = {}
        role_bans: dict[str, int] = {}

        for role_key, tab in self.role_tabs.items():
            spells = tab.first_spell_pair()
            if spells is not None:
                role_summoner_spells[role_key] = spells

            champion_ids = tab.champion_ids()
            if champion_ids:
                role_champions[role_key] = [cid for cid in champion_ids if cid is not None]

            if tab.ban_id is not None:
                role_bans[role_key] = tab.ban_id

        # Used when champion select has not assigned a position yet.
        fallback = role_summoner_spells.get(str(primary_role or "").upper()) or {}

        return {
            "queue_id": int(QUEUE_MODES.get(self.queue_combo.currentText(), DEFAULT_QUEUE_ID)),
            "primary_role": primary_role,
            "secondary_role": secondary_role,
            "primary_summoner_spell": fallback.get("spell1Id"),
            "secondary_summoner_spell": fallback.get("spell2Id"),
            "role_summoner_spells": role_summoner_spells,
            "custom_summoner_spells": config.custom_summoner_spells,
            "role_champions": role_champions,
            "role_bans": role_bans,
            "custom_runes": config.custom_runes,
            "rune_selection": config.rune_selection,
            "role_rune_selection": config.role_rune_selection,
            "custom_skins": config.custom_skins,
        }

    def _render_automation_state(self, state: str, tooltip: str) -> None:
        visuals = _STATE_VISUALS.get(state, _STATE_VISUALS[STATE_CHECKING])

        self.start_button.setText(visuals.start_text)
        self.start_button.setIcon(self._icons[visuals.start_icon])
        self.start_button.setEnabled(
            visuals.start_enabled and self.settings.ready and self._champions_loaded
        )

        self.stop_button.setText(visuals.stop_text)
        self.stop_button.setIcon(self._icons[visuals.stop_icon])
        self.stop_button.setEnabled(visuals.stop_enabled)

        self.automation_status.setText(visuals.badge)
        self.automation_status.setToolTip(tooltip)
        self.corner_status_label.setText(visuals.corner)
        self.corner_status_label.setToolTip(f"Status: {visuals.corner}")

        if visuals.busy:
            self.corner_progress.setRange(0, 0)
        else:
            self.corner_progress.setRange(0, 1)
            self.corner_progress.setValue(1 if state == STATE_RUNNING else 0)

        for widget, prop in (
            (self.start_button, "automationState"),
            (self.stop_button, "automationState"),
            (self.automation_status, "state"),
            (self.corner_status_label, "state"),
            (self.corner_progress, "state"),
        ):
            widget.setProperty(prop, state)
            _repolish(widget)

    def _show_notification(self, level: str, title: str, message: str) -> None:
        if level == "error":
            QMessageBox.critical(self, title, message)
        else:
            QMessageBox.information(self, title, message)

    # -- updates -------------------------------------------------------------

    def _on_update_available(self, info_obj: object) -> None:
        info: UpdateInfo = info_obj  # type: ignore[assignment]

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Update Available")
        box.setText(
            f"A new version of {APP_DISPLAY_NAME} is available.\n\n"
            f"Installed: {info.current_version}\n"
            f"New: {info.latest_version}"
        )
        if info.release_notes:
            box.setDetailedText(info.release_notes)

        label = "Update" if info.asset_download_url else "Open Release Page"
        primary = box.addButton(label, QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(primary)
        box.exec()

        if box.clickedButton() != primary:
            return
        if info.asset_download_url:
            self.updater.download(info)
        else:
            self.updater.open_release_page(info)

    def _show_download_progress(self) -> None:
        dialog = QProgressDialog("Downloading update...", None, 0, 0, self)
        dialog.setWindowTitle("Update")
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.setCancelButton(None)
        dialog.setMinimumDuration(0)
        dialog.show()
        self._update_progress = dialog

    def _on_download_finished(self, ok: bool, path: str, error: str) -> None:
        if self._update_progress is not None:
            self._update_progress.close()
            self._update_progress = None

        if not ok:
            QMessageBox.critical(
                self, "Update", f"Update download failed:\n\n{error or 'Unknown error'}"
            )
            return

        try:
            self.updater.launch_installer(path)
        except Exception as e:
            QMessageBox.critical(self, "Update", f"Could not launch installer:\n\n{e}")
            return

        self.close()

    # -- game phase & tray ---------------------------------------------------

    def check_game_phase(self) -> None:
        self.phase_query.run(self._client.gameflow)

    def _on_game_phase(self, status: GameflowStatus) -> None:
        phase = status.phase
        if phase is None or phase == self.last_phase:
            return

        print(f"[GAMEFLOW] phase={phase}")
        previous = self.last_phase
        self.last_phase = phase
        if phase in ("GameStart", "InProgress") and previous not in ("GameStart", "InProgress"):
            self.notifier.show(APP_DISPLAY_NAME, "Game started! Selections applied.")

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def changeEvent(self, event) -> None:
        """Hides to the system tray when minimized, so automation keeps running."""
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            self.hide()
            self.tray_icon.showMessage(
                APP_DISPLAY_NAME,
                "RunePilot continues running in the background.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
        super().changeEvent(event)

    def closeEvent(self, event) -> None:
        if self._allow_close or not self.settings.ready or not self._champions_loaded:
            self.updater.shutdown()
            self.settings.shutdown()
            self.champions_query.shutdown()
            self.phase_query.shutdown()
            for tab in self.role_tabs.values():
                tab.shutdown()
            self.phase_timer.stop()
            self.automation.stop_polling()
            super().closeEvent(event)
            return
        event.ignore()
        if self._closing:
            return
        self._closing = True
        self.centralWidget().setEnabled(False)
        self.save_config()
        self.settings.flush()


def _title_label(text: str, object_name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    return label


def _repolish(widget: QWidget) -> None:
    """Re-applies the stylesheet after a dynamic property changed."""
    try:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
    except Exception:
        pass
    widget.update()


def main() -> None:
    """Launches the desktop application (Qt event loop)."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    try:
        app.setApplicationDisplayName(APP_DISPLAY_NAME)
        app.setApplicationName(APP_ID)
        app.setApplicationVersion(__version__)
        app.setWindowIcon(QIcon(resource_path("assets/app_icon.png")))
    except Exception:
        pass

    client = ApiClient()
    main_window = MainWindow(api_client=client)
    main_window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
