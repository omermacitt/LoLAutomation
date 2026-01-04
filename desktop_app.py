"""
RunePilot masaüstü uygulaması (PyQt6).

Kullanıcıdan rol/ban/şampiyon tercihlerini alır, `api.py` üzerindeki FastAPI
servisine gönderir ve otomasyonu kontrol eder.
"""
import sys
import os
import json
import threading
import tempfile
import webbrowser
import requests

from app_meta import (
    APP_DISPLAY_NAME,
    APP_ID,
    LEGACY_APP_ID,
    LEGACY_CONFIG_FILE,
    UPDATE_REPO_DEFAULT,
    __version__,
)
from updater import UpdateInfo, check_for_update, download_asset

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCompleter,
    QDialog,
    QMainWindow,
    QWidget,
    QLabel,
    QComboBox,
    QPushButton,
    QGridLayout,
    QMessageBox,
    QHBoxLayout,
    QVBoxLayout,
    QTabWidget,
    QGroupBox,
    QFormLayout,
    QProgressBar,
    QProgressDialog,
    QStyle,
)
from PyQt6.QtCore import Qt, QTimer, QObject, QEvent, pyqtSignal, QSize

from win10toast import ToastNotifier

from lcu import lcu_request  # mevcut projenizdeki lcu.py'den
from skins_dialog import SkinSelectDialog
from rune_presets_dialog import RunePresetsDialog

API_BASE = "http://127.0.0.1:8000"  # FastAPI sunucunun adresi
API_TIMEOUT_SEC = 3

class _SearchableComboLineEditFilter(QObject):
    def __init__(self, combo: QComboBox):
        super().__init__(combo)
        self._combo = combo

    def eventFilter(self, obj, event):
        try:
            etype = event.type()
        except Exception:
            return False

        if etype in (QEvent.Type.FocusIn, QEvent.Type.MouseButtonPress):
            QTimer.singleShot(0, obj.selectAll)
            return False

        if etype == QEvent.Type.KeyPress:
            try:
                text = event.text() or ""
            except Exception:
                text = ""

            try:
                modifiers = event.modifiers()
            except Exception:
                modifiers = Qt.KeyboardModifier.NoModifier

            if text and not (
                modifiers
                & (
                    Qt.KeyboardModifier.ControlModifier
                    | Qt.KeyboardModifier.AltModifier
                    | Qt.KeyboardModifier.MetaModifier
                )
            ):
                try:
                    current_item_text = self._combo.itemText(self._combo.currentIndex())
                except Exception:
                    current_item_text = ""
                try:
                    le_text = obj.text() or ""
                except Exception:
                    le_text = ""

                if le_text == current_item_text and not obj.hasSelectedText():
                    obj.selectAll()

        return False


class _UpdateEmitter(QObject):
    update_available = pyqtSignal(object)
    download_finished = pyqtSignal(bool, str, str)

class _HealthEmitter(QObject):
    checked = pyqtSignal(bool, bool, str)


def make_combo_searchable(combo: QComboBox, *, placeholder: str = "Ara...") -> None:
    """QComboBox'a yaz-ara (type-ahead) davranışı ekler."""
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    combo.setMaxVisibleItems(20)

    le = combo.lineEdit()
    if le is None:
        return

    le.setPlaceholderText(placeholder)
    filter_obj = _SearchableComboLineEditFilter(combo)
    le.installEventFilter(filter_obj)
    setattr(combo, "_search_event_filter", filter_obj)

    completer = QCompleter(combo.model(), combo)
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    completer.activated[str].connect(lambda text, cb=combo: cb.setCurrentIndex(cb.findText(text)))
    combo.setCompleter(completer)

    def restore_valid_text(cb: QComboBox = combo, line_edit=le) -> None:
        try:
            typed = (line_edit.text() or "").strip()
        except Exception:
            typed = ""

        try:
            current_idx = cb.currentIndex()
        except Exception:
            current_idx = 0

        def set_display_to_current() -> None:
            try:
                line_edit.setText(cb.itemText(current_idx))
            except Exception:
                pass

        if not typed:
            set_display_to_current()
            return

        typed_cf = typed.casefold()
        match_idx = -1
        for i in range(cb.count()):
            if cb.itemText(i).casefold() == typed_cf:
                match_idx = i
                break

        if match_idx >= 0:
            cb.setCurrentIndex(match_idx)
            return

        set_display_to_current()

    le.editingFinished.connect(restore_valid_text)

def resource_path(relative_path: str) -> str:
    """
    Get absolute path to a bundled resource, works for dev and for PyInstaller.
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

def get_config_file_path(app_id: str) -> str:
    """Kullanıcı ayar dosyasının (JSON) lokasyonunu döndürür."""
    base_dir = os.getenv("APPDATA") or os.path.expanduser("~")
    return os.path.join(base_dir, app_id, "user_config.json")

CONFIG_FILE = get_config_file_path(APP_ID)
LEGACY_APP_CONFIG_FILE = get_config_file_path(LEGACY_APP_ID)

QUEUE_MODES = {
    "Normal Draft": 400,
    "Ranked Solo/Duo": 420,
    "Ranked Flex": 440,
}

ROLES = {
    "Yok": None,
    "Top": "TOP",
    "Jungle": "JUNGLE",
    "Mid": "MIDDLE",
    "ADC": "BOTTOM",
    "Support": "UTILITY",
}

SUMMONER_SPELLS = {
    "Yok": None,
    "Sıçra (Flash)": 4,
    "Tutuştur (Ignite)": 14,
    "Işınlan (Teleport)": 12,
    "Hayalet (Ghost)": 6,
    "İyileştirme (Heal)": 7,
    "Çarp (Smite)": 11,
    "Bitkinlik (Exhaust)": 3,
    "Bariyer (Barrier)": 21,
    "Arındır (Cleanse)": 1,
}

SPELL_NAME_BY_ID = {v: k for k, v in SUMMONER_SPELLS.items() if v is not None}


class MainWindow(QMainWindow):
    """RunePilot ana pencere UI'si."""
    def __init__(self):
        super().__init__()

        self.setWindowTitle(f"{APP_DISPLAY_NAME} – Rol Bazlı Seçim")
        try:
            self.setWindowIcon(QIcon(resource_path("assets/app_icon.png")))
        except Exception:
            pass
        self.resize(700, 500)

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Sağ üst durum/progress göstergesi
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        top_row.addStretch(1)

        self.corner_status_label = QLabel("Kontrol…")
        self.corner_status_label.setObjectName("cornerStatusLabel")
        self.corner_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.corner_status_label.setProperty("state", "checking")
        self.corner_status_label.setToolTip("Otomasyon durumu")

        self.corner_progress = QProgressBar()
        self.corner_progress.setObjectName("cornerProgress")
        self.corner_progress.setTextVisible(False)
        self.corner_progress.setFixedSize(90, 10)
        self.corner_progress.setRange(0, 0)  # indeterminate
        self.corner_progress.setProperty("state", "checking")

        corner_container = QWidget()
        corner_layout = QHBoxLayout(corner_container)
        corner_layout.setContentsMargins(0, 0, 0, 0)
        corner_layout.setSpacing(6)
        corner_layout.addWidget(self.corner_status_label)
        corner_layout.addWidget(self.corner_progress)

        top_row.addWidget(corner_container, alignment=Qt.AlignmentFlag.AlignRight)
        main_layout.addLayout(top_row)

        title = QLabel(APP_DISPLAY_NAME)
        title.setObjectName("appTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        subtitle = QLabel("Rol bazlı ban / şampiyon seçimi & rün otomasyonu")
        subtitle.setObjectName("appSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)

        # ---------------------------------------------------------------------
        # 1. Genel Ayarlar (Queue, Roller)
        # ---------------------------------------------------------------------
        settings_group = QGroupBox("Genel Ayarlar")
        settings_layout = QGridLayout(settings_group)

        # Queue
        settings_layout.addWidget(QLabel("Oyun Modu:"), 0, 0)
        self.queue_combo = QComboBox()
        for name in QUEUE_MODES.keys():
            self.queue_combo.addItem(name)
        self.queue_combo.setCurrentText("Ranked Solo/Duo")
        settings_layout.addWidget(self.queue_combo, 0, 1)

        # Roller
        settings_layout.addWidget(QLabel("1. Tercih:"), 1, 0)
        self.primary_role_combo = QComboBox()
        settings_layout.addWidget(self.primary_role_combo, 1, 1)

        settings_layout.addWidget(QLabel("2. Tercih:"), 1, 2)
        self.secondary_role_combo = QComboBox()
        settings_layout.addWidget(self.secondary_role_combo, 1, 3)

        # Doldur
        for name in ROLES.keys():
            self.primary_role_combo.addItem(name)
            self.secondary_role_combo.addItem(name)
        self.primary_role_combo.setCurrentText("Top")
        self.secondary_role_combo.setCurrentText("Jungle")

        self._updating_role_preferences = False
        self.primary_role_combo.currentIndexChanged.connect(lambda _=0: self.on_role_preference_changed("primary"))
        self.secondary_role_combo.currentIndexChanged.connect(lambda _=0: self.on_role_preference_changed("secondary"))
        self._refresh_role_preference_exclusion()

        main_layout.addWidget(settings_group)

        # ---------------------------------------------------------------------
        # 2. Rol Bazlı Şampiyon Seçimi (Tabs)
        # ---------------------------------------------------------------------
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Her rol için 3 combo box tutacağız
        # self.role_widgets[role_key] = [combo1, combo2, combo3]
        self.role_combos = {}
        self.role_ban_combos = {}
        self.role_rune_buttons = {}
        self.role_rune_select_combos = {}
        self.role_skin_buttons = {}
        # role -> [ (spell1_combo, spell2_combo), ... ] (champion rows)
        self.role_champion_spell_combos = {}
        # champId(str) -> slot(str: "1"|"2"|"3") -> rune page dict
        self.custom_runes = {}
        # champId(str) -> 0(recommended) | 1 | 2 | 3
        self.rune_selection = {}
        # role -> champId(str) -> skinId(int)
        self.custom_skins = {}
        # role -> champId(str) -> {"spell1Id": int|None, "spell2Id": int|None}
        self.custom_summoner_spells = {}
        self._updating_champion_spells = False

        # ROLES mapping order for tabs
        # "Top", "Jungle", "Mid", "ADC", "Support"
        role_tab_order = [
            ("Top", "TOP"),
            ("Jungle", "JUNGLE"),
            ("Mid", "MIDDLE"),
            ("ADC", "BOTTOM"),
            ("Support", "UTILITY"),
        ]

        for display_name, role_key in role_tab_order:
            page = QWidget()
            layout = QFormLayout(page)

            ban_combo = QComboBox()
            combo1 = QComboBox()
            combo2 = QComboBox()
            combo3 = QComboBox()

            make_combo_searchable(ban_combo, placeholder="Ban ara...")
            make_combo_searchable(combo1)
            make_combo_searchable(combo2)
            make_combo_searchable(combo3)

            layout.addRow("Ban Şampiyonu:", ban_combo)

            layout.addRow("1. Şampiyon (En öncelikli):", self._make_champion_row(role_key, 0, combo1))
            layout.addRow("2. Şampiyon:", self._make_champion_row(role_key, 1, combo2))
            layout.addRow("3. Şampiyon:", self._make_champion_row(role_key, 2, combo3))

            self.tabs.addTab(page, display_name)
            self.role_combos[role_key] = [combo1, combo2, combo3]
            self.role_ban_combos[role_key] = ban_combo

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self._icon_play = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        self._icon_stop = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop)
        self._icon_running = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
        self._icon_wait = self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)

        self.start_button = QPushButton("Başlat")
        self.start_button.setObjectName("startButton")
        self.start_button.setIcon(self._icon_play)
        self.start_button.setIconSize(QSize(18, 18))
        self.start_button.setToolTip("Otomasyonu başlatır")
        self.start_button.clicked.connect(self.start_automation)
        self.start_button.setFixedHeight(40)
        self.start_button.setProperty("automationState", "stopped")
        button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Durdur")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setIcon(self._icon_stop)
        self.stop_button.setIconSize(QSize(18, 18))
        self.stop_button.setToolTip("Otomasyonu durdurur")
        self.stop_button.clicked.connect(self.stop_automation)
        self.stop_button.setFixedHeight(40)
        self.stop_button.setEnabled(False) # Başlangıçta pasif
        self.stop_button.setProperty("automationState", "stopped")
        button_layout.addWidget(self.stop_button)

        self.automation_status = QLabel("Durum: Kontrol ediliyor…")
        self.automation_status.setObjectName("automationStatus")
        self.automation_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.automation_status.setFixedHeight(32)
        self.automation_status.setProperty("state", "checking")
        button_layout.addStretch(1)
        button_layout.addWidget(self.automation_status)

        main_layout.addLayout(button_layout)

        # Şampiyon listesini yenile butonu (üstte, genel ayarlar yanında)
        self.refresh_button = QPushButton("Şampiyonları Yenile")
        self.refresh_button.setObjectName("refreshButton")
        self.refresh_button.clicked.connect(self.refresh_champions)
        self.refresh_button.setFixedHeight(32)
        settings_layout.addWidget(self.refresh_button, 0, 2, 1, 2)

        # Veri yükle
        self.load_champions()

        # Kayıtlı ayarları yükle (şampiyonlar yüklendikten sonra yapılmalı)
        self.load_config()

        # Bildirim
        self.toaster = ToastNotifier()
        self.last_phase = None
        self.phase_timer = QTimer(self)
        self.phase_timer.timeout.connect(self.check_game_phase)
        self.phase_timer.start(2000)

        self._health_emitter = _HealthEmitter()
        self._health_emitter.checked.connect(self._on_health_checked)
        self._health_check_inflight = False
        self._automation_action_inflight = False
        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self._check_health_async)
        self._health_timer.start(4000)
        self._check_health_async()

        self._automation_state = "checking"
        self._live_config_push_timer = QTimer(self)
        self._live_config_push_timer.setSingleShot(True)
        self._live_config_push_timer.timeout.connect(self._push_live_config_to_api)

        # Otomatik güncelleme kontrolü (GitHub Releases)
        self._update_emitter = _UpdateEmitter()
        self._update_emitter.update_available.connect(self._on_update_available)
        self._update_emitter.download_finished.connect(self._on_update_download_finished)
        self._update_progress_dialog: QProgressDialog | None = None
        self._update_check_started = False
        self._schedule_update_check()

    def _repolish(self, widget: QWidget) -> None:
        try:
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        except Exception:
            pass
        widget.update()

    def _set_corner_status_state(self, state: str) -> None:
        if not hasattr(self, "corner_status_label") or not hasattr(self, "corner_progress"):
            return

        if state == "running":
            text = "Çalışıyor"
            self.corner_progress.setRange(0, 1)
            self.corner_progress.setValue(1)
        elif state == "stopped":
            text = "Durduruldu"
            self.corner_progress.setRange(0, 1)
            self.corner_progress.setValue(0)
        elif state == "offline":
            text = "Sunucu yok"
            self.corner_progress.setRange(0, 1)
            self.corner_progress.setValue(0)
        elif state == "starting":
            text = "Başlıyor…"
            self.corner_progress.setRange(0, 0)
        elif state == "stopping":
            text = "Duruyor…"
            self.corner_progress.setRange(0, 0)
        else:
            state = "checking"
            text = "Kontrol…"
            self.corner_progress.setRange(0, 0)

        self.corner_status_label.setText(text)
        self.corner_status_label.setProperty("state", state)
        self.corner_progress.setProperty("state", state)
        self.corner_status_label.setToolTip(f"Durum: {text}")

        self._repolish(self.corner_status_label)
        self._repolish(self.corner_progress)

    def _set_automation_ui_state(self, state: str, *, detail: str | None = None) -> None:
        """
        UI state'ini tek noktadan günceller.

        state: checking | offline | stopped | running | starting | stopping
        """
        if state == "running":
            self.start_button.setText("Çalışıyor")
            self.start_button.setIcon(self._icon_running)
            self.start_button.setEnabled(False)

            self.stop_button.setText("Durdur")
            self.stop_button.setIcon(self._icon_stop)
            self.stop_button.setEnabled(True)

            badge_text = detail or "Durum: Çalışıyor"
        elif state == "stopped":
            self.start_button.setText("Başlat")
            self.start_button.setIcon(self._icon_play)
            self.start_button.setEnabled(True)

            self.stop_button.setText("Durdur")
            self.stop_button.setIcon(self._icon_stop)
            self.stop_button.setEnabled(False)

            badge_text = detail or "Durum: Durduruldu"
        elif state == "offline":
            self.start_button.setText("Başlat")
            self.start_button.setIcon(self._icon_play)
            self.start_button.setEnabled(True)

            self.stop_button.setText("Durdur")
            self.stop_button.setIcon(self._icon_stop)
            self.stop_button.setEnabled(False)

            badge_text = detail or "Durum: Sunucu kapalı"
        elif state == "starting":
            self.start_button.setText("Başlatılıyor…")
            self.start_button.setIcon(self._icon_wait)
            self.start_button.setEnabled(False)

            self.stop_button.setText("Durdur")
            self.stop_button.setIcon(self._icon_stop)
            self.stop_button.setEnabled(False)

            badge_text = detail or "Durum: Başlatılıyor…"
        elif state == "stopping":
            self.start_button.setText("Çalışıyor")
            self.start_button.setIcon(self._icon_running)
            self.start_button.setEnabled(False)

            self.stop_button.setText("Durduruluyor…")
            self.stop_button.setIcon(self._icon_wait)
            self.stop_button.setEnabled(False)

            badge_text = detail or "Durum: Durduruluyor…"
        else:
            # checking / unknown fallback
            self.start_button.setText("Başlat")
            self.start_button.setIcon(self._icon_play)
            self.start_button.setEnabled(True)

            self.stop_button.setText("Durdur")
            self.stop_button.setIcon(self._icon_stop)
            self.stop_button.setEnabled(False)

            badge_text = detail or "Durum: Kontrol ediliyor…"
            state = "checking"

        self.start_button.setProperty("automationState", state)
        self.stop_button.setProperty("automationState", state)
        self.automation_status.setProperty("state", state)
        self.automation_status.setText(badge_text)
        self._automation_state = state

        self._repolish(self.start_button)
        self._repolish(self.stop_button)
        self._repolish(self.automation_status)
        self._set_corner_status_state(state)

    def _check_health_async(self) -> None:
        if self._automation_action_inflight or self._health_check_inflight:
            return

        self._health_check_inflight = True

        def worker() -> None:
            ok = False
            running = False
            err = ""
            try:
                resp = requests.get(f"{API_BASE}/health", timeout=API_TIMEOUT_SEC)
                if resp.status_code == 200:
                    data = resp.json() or {}
                    ok = True
                    running = bool(data.get("running"))
                else:
                    err = f"HTTP {resp.status_code}"
            except Exception as e:
                err = str(e)

            self._health_emitter.checked.emit(bool(ok), bool(running), str(err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_health_checked(self, ok: bool, running: bool, err: str) -> None:
        self._health_check_inflight = False
        if self._automation_action_inflight:
            return

        if not ok:
            self.automation_status.setToolTip(err or "")
            self._set_automation_ui_state("offline")
            return

        self.automation_status.setToolTip("Sunucu çalışıyor")
        self._set_automation_ui_state("running" if running else "stopped")

    def _set_combo_item_enabled(self, combo: QComboBox, index: int, enabled: bool) -> None:
        model = combo.model()
        try:
            item = model.item(index)  # type: ignore[attr-defined]
        except Exception:
            item = None
        if item is None:
            return
        try:
            item.setEnabled(bool(enabled))
        except Exception:
            return

    def _refresh_role_preference_exclusion(self) -> None:
        def reset_all(combo: QComboBox) -> None:
            for i in range(combo.count()):
                self._set_combo_item_enabled(combo, i, True)

        reset_all(self.primary_role_combo)
        reset_all(self.secondary_role_combo)

        primary_name = self.primary_role_combo.currentText()
        secondary_name = self.secondary_role_combo.currentText()

        if primary_name != "Yok":
            idx = self.secondary_role_combo.findText(primary_name)
            if idx >= 0:
                self._set_combo_item_enabled(self.secondary_role_combo, idx, False)

        if secondary_name != "Yok":
            idx = self.primary_role_combo.findText(secondary_name)
            if idx >= 0:
                self._set_combo_item_enabled(self.primary_role_combo, idx, False)

    def on_role_preference_changed(self, changed: str) -> None:
        if self._updating_role_preferences:
            return

        self._updating_role_preferences = True
        try:
            primary_name = self.primary_role_combo.currentText()
            secondary_name = self.secondary_role_combo.currentText()

            if primary_name != "Yok" and secondary_name != "Yok" and primary_name == secondary_name:
                if changed == "primary":
                    self.secondary_role_combo.setCurrentText("Yok")
                else:
                    self.primary_role_combo.setCurrentText("Yok")

            self._refresh_role_preference_exclusion()
        finally:
            self._updating_role_preferences = False

    def _refresh_spell_exclusion(self, spell1_combo: QComboBox, spell2_combo: QComboBox) -> None:
        for i in range(spell1_combo.count()):
            self._set_combo_item_enabled(spell1_combo, i, True)
        for i in range(spell2_combo.count()):
            self._set_combo_item_enabled(spell2_combo, i, True)

        spell1_name = spell1_combo.currentText()
        spell2_name = spell2_combo.currentText()

        if spell1_name != "Yok":
            idx = spell2_combo.findText(spell1_name)
            if idx >= 0:
                self._set_combo_item_enabled(spell2_combo, idx, False)

        if spell2_name != "Yok":
            idx = spell1_combo.findText(spell2_name)
            if idx >= 0:
                self._set_combo_item_enabled(spell1_combo, idx, False)

    def _get_champion_spell_pair(self, role_key: str, index: int) -> tuple[QComboBox, QComboBox] | None:
        rows = self.role_champion_spell_combos.get(role_key)
        if not rows or not isinstance(rows, list) or index >= len(rows):
            return None
        pair = rows[index]
        if not pair or not isinstance(pair, (tuple, list)) or len(pair) != 2:
            return None
        spell1_combo, spell2_combo = pair
        if not isinstance(spell1_combo, QComboBox) or not isinstance(spell2_combo, QComboBox):
            return None
        return spell1_combo, spell2_combo

    def _spell_name_from_id(self, spell_id: int | None) -> str:
        if spell_id is None:
            return "Yok"
        return SPELL_NAME_BY_ID.get(int(spell_id), "Yok")

    def _default_spell_names_for_role(self, role_key: str) -> tuple[str, str]:
        if role_key == "JUNGLE":
            return "Sıçra (Flash)", "Çarp (Smite)"
        return "Sıçra (Flash)", "Tutuştur (Ignite)"

    def _normalize_spell_id_from_any(self, value) -> int | None:
        if value is None:
            return None
        if isinstance(value, str) and value in SUMMONER_SPELLS:
            return SUMMONER_SPELLS.get(value)
        try:
            sid = int(value)
        except (TypeError, ValueError):
            return None
        return sid if sid > 0 else None

    def update_champion_spell_row(self, role_key: str, index: int) -> None:
        pair = self._get_champion_spell_pair(role_key, index)
        if pair is None:
            return
        spell1_combo, spell2_combo = pair

        combos = self.role_combos.get(role_key) or []
        champ_id = combos[index].currentData() if index < len(combos) else None
        if not champ_id:
            spell1_combo.setEnabled(False)
            spell2_combo.setEnabled(False)
            return

        cid = str(champ_id)
        role_map = self.custom_summoner_spells.get(role_key)
        role_map = role_map if isinstance(role_map, dict) else {}
        entry = role_map.get(cid)

        has_s1 = False
        has_s2 = False
        s1_id: int | None = None
        s2_id: int | None = None

        if isinstance(entry, dict):
            if "spell1Id" in entry or "spell1" in entry:
                has_s1 = True
            if "spell2Id" in entry or "spell2" in entry:
                has_s2 = True

            if "spell1Id" in entry:
                s1_id = self._normalize_spell_id_from_any(entry.get("spell1Id"))
            elif "spell1" in entry:
                s1_id = self._normalize_spell_id_from_any(entry.get("spell1"))

            if "spell2Id" in entry:
                s2_id = self._normalize_spell_id_from_any(entry.get("spell2Id"))
            elif "spell2" in entry:
                s2_id = self._normalize_spell_id_from_any(entry.get("spell2"))
        elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
            has_s1 = True
            has_s2 = True
            s1_id = self._normalize_spell_id_from_any(entry[0])
            s2_id = self._normalize_spell_id_from_any(entry[1])

        if not has_s1 or not has_s2:
            default_s1_name, default_s2_name = self._default_spell_names_for_role(role_key)
            if not has_s1:
                s1_id = SUMMONER_SPELLS.get(default_s1_name)
            if not has_s2:
                s2_id = SUMMONER_SPELLS.get(default_s2_name)

        self.custom_summoner_spells.setdefault(role_key, {})[cid] = {
            "spell1Id": s1_id,
            "spell2Id": s2_id,
        }

        self._updating_champion_spells = True
        try:
            spell1_combo.setEnabled(True)
            spell2_combo.setEnabled(True)
            spell1_combo.setCurrentText(self._spell_name_from_id(s1_id))
            spell2_combo.setCurrentText(self._spell_name_from_id(s2_id))

            if (
                spell1_combo.currentText() != "Yok"
                and spell2_combo.currentText() != "Yok"
                and spell1_combo.currentText() == spell2_combo.currentText()
            ):
                spell2_combo.setCurrentText("Yok")
                self.custom_summoner_spells.setdefault(role_key, {})[cid]["spell2Id"] = None

            self._refresh_spell_exclusion(spell1_combo, spell2_combo)
        finally:
            self._updating_champion_spells = False

    def on_champion_spell_changed(self, role_key: str, index: int, changed: str) -> None:
        if self._updating_champion_spells:
            return

        pair = self._get_champion_spell_pair(role_key, index)
        if pair is None:
            return
        spell1_combo, spell2_combo = pair

        combos = self.role_combos.get(role_key) or []
        champ_id = combos[index].currentData() if index < len(combos) else None
        if not champ_id:
            return

        cid = str(champ_id)

        self._updating_champion_spells = True
        try:
            spell1_name = spell1_combo.currentText()
            spell2_name = spell2_combo.currentText()
            if spell1_name != "Yok" and spell2_name != "Yok" and spell1_name == spell2_name:
                if changed == "spell1":
                    spell2_combo.setCurrentText("Yok")
                else:
                    spell1_combo.setCurrentText("Yok")

            self._refresh_spell_exclusion(spell1_combo, spell2_combo)
        finally:
            self._updating_champion_spells = False

        self.custom_summoner_spells.setdefault(role_key, {})[cid] = {
            "spell1Id": SUMMONER_SPELLS.get(spell1_combo.currentText()),
            "spell2Id": SUMMONER_SPELLS.get(spell2_combo.currentText()),
        }

        for i in range(3):
            if i == index:
                continue
            other_combo = (self.role_combos.get(role_key) or [None, None, None])[i]
            if other_combo is not None and other_combo.currentData() == champ_id:
                self.update_champion_spell_row(role_key, i)

    def _sync_custom_summoner_spells_from_ui(self) -> dict[str, dict[str, dict[str, int | None]]]:
        current = self.custom_summoner_spells if isinstance(self.custom_summoner_spells, dict) else {}

        for role_key, combos in (self.role_combos or {}).items():
            for i, champ_combo in enumerate(combos):
                champ_id = champ_combo.currentData()
                if not champ_id:
                    continue
                pair = self._get_champion_spell_pair(role_key, i)
                if pair is None:
                    continue
                spell1_combo, spell2_combo = pair
                current.setdefault(role_key, {})[str(champ_id)] = {
                    "spell1Id": SUMMONER_SPELLS.get(spell1_combo.currentText()),
                    "spell2Id": SUMMONER_SPELLS.get(spell2_combo.currentText()),
                }

        self.custom_summoner_spells = current
        return current

    def update_all_champion_spell_rows(self) -> None:
        for role_key, combos in (self.role_combos or {}).items():
            for i in range(min(3, len(combos))):
                self.update_champion_spell_row(role_key, i)

    def _make_champion_row(self, role_key: str, index: int, combo: QComboBox) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(combo, 1)

        spell1_combo = QComboBox()
        spell2_combo = QComboBox()
        for name in SUMMONER_SPELLS.keys():
            spell1_combo.addItem(name)
            spell2_combo.addItem(name)

        spell1_combo.setToolTip("1. Büyü")
        spell2_combo.setToolTip("2. Büyü")
        spell1_combo.setCurrentText("Sıçra (Flash)")
        if role_key == "JUNGLE":
            spell2_combo.setCurrentText("Çarp (Smite)")
        else:
            spell2_combo.setCurrentText("Tutuştur (Ignite)")

        spell1_combo.setFixedWidth(155)
        spell2_combo.setFixedWidth(155)
        spell1_combo.setEnabled(False)
        spell2_combo.setEnabled(False)

        self.role_champion_spell_combos.setdefault(role_key, [None, None, None])
        self.role_champion_spell_combos[role_key][index] = (spell1_combo, spell2_combo)

        spell1_combo.currentIndexChanged.connect(
            lambda _=0, rk=role_key, i=index: self.on_champion_spell_changed(rk, i, "spell1")
        )
        spell2_combo.currentIndexChanged.connect(
            lambda _=0, rk=role_key, i=index: self.on_champion_spell_changed(rk, i, "spell2")
        )
        self._refresh_spell_exclusion(spell1_combo, spell2_combo)

        row_layout.addWidget(spell1_combo)
        row_layout.addWidget(spell2_combo)

        rune_select = QComboBox()
        rune_select.setFixedWidth(140)
        rune_select.setToolTip("Bu şampiyon için kullanılacak rün sayfası")
        rune_select.currentIndexChanged.connect(
            lambda _=0, rk=role_key, i=index: self.on_rune_selection_changed(rk, i)
        )
        row_layout.addWidget(rune_select)

        self.role_rune_select_combos.setdefault(role_key, [None, None, None])
        self.role_rune_select_combos[role_key][index] = rune_select

        button = QPushButton("Rünler")
        button.setObjectName("runeButton")
        button.setFixedWidth(95)
        button.clicked.connect(lambda _=False, rk=role_key, i=index: self.open_rune_presets_dialog(rk, i))
        row_layout.addWidget(button)

        self.role_rune_buttons.setdefault(role_key, [None, None, None])
        self.role_rune_buttons[role_key][index] = button

        skin_button = QPushButton("Kostüm")
        skin_button.setObjectName("skinButton")
        skin_button.setFixedWidth(95)
        skin_button.clicked.connect(lambda _=False, rk=role_key, i=index: self.edit_custom_skin(rk, i))
        row_layout.addWidget(skin_button)

        self.role_skin_buttons.setdefault(role_key, [None, None, None])
        self.role_skin_buttons[role_key][index] = skin_button

        combo.currentIndexChanged.connect(lambda _=0, rk=role_key, i=index: self.on_champion_changed(rk, i))
        self.update_rune_button(role_key, index)
        self.update_rune_select_combo(role_key, index)
        self.update_skin_button(role_key, index)
        return row

    def update_rune_button(self, role_key: str, index: int) -> None:
        buttons = self.role_rune_buttons.get(role_key) or []
        if index >= len(buttons) or buttons[index] is None:
            return
        button = buttons[index]

        combos = self.role_combos.get(role_key) or []
        if index >= len(combos):
            return
        champ_id = combos[index].currentData()

        if not champ_id:
            button.setEnabled(False)
            button.setText("Rünler")
            button.setToolTip("")
            self._set_button_configured(button, False)
            return

        button.setEnabled(True)
        presets = self.custom_runes.get(str(champ_id))
        presets = presets if isinstance(presets, dict) else {}
        preset_count = sum(1 for k, v in presets.items() if str(k) in ("1", "2", "3") and isinstance(v, dict))
        self._set_button_configured(button, preset_count > 0)
        button.setText(f"Rünler ({preset_count})" if preset_count else "Rünler")
        button.setToolTip(
            f"{preset_count} adet özel rün preset'i kaydedildi" if preset_count else "Önerilen rün kullanılacak"
        )

    def update_all_rune_buttons(self) -> None:
        for role_key, buttons in (self.role_rune_buttons or {}).items():
            for i in range(min(3, len(buttons))):
                self.update_rune_button(role_key, i)

    def update_rune_select_combo(self, role_key: str, index: int) -> None:
        select_combos = self.role_rune_select_combos.get(role_key) or []
        if index >= len(select_combos) or select_combos[index] is None:
            return
        select_combo = select_combos[index]

        combos = self.role_combos.get(role_key) or []
        if index >= len(combos):
            return
        champ_id = combos[index].currentData()

        select_combo.blockSignals(True)
        try:
            select_combo.clear()
            select_combo.addItem("Önerilen", 0)

            if not champ_id:
                select_combo.setEnabled(False)
                select_combo.setCurrentIndex(0)
                return

            champ_key = str(champ_id)
            presets = self.custom_runes.get(champ_key)
            presets = presets if isinstance(presets, dict) else {}
            for slot in (1, 2, 3):
                page = presets.get(str(slot))
                if isinstance(page, dict):
                    raw_name = page.get("name")
                    name = str(raw_name).strip() if raw_name is not None else ""
                    name = " ".join(name.split())
                    label = f"Özel {slot}: {name}" if name else f"Özel {slot}"
                    select_combo.addItem(label, slot)

            raw_selection = self.rune_selection.get(champ_key, 0) if isinstance(self.rune_selection, dict) else 0
            try:
                selection = int(raw_selection or 0)
            except (TypeError, ValueError):
                selection = 0
            if selection not in (0, 1, 2, 3):
                selection = 0
            if selection != 0 and str(selection) not in presets:
                selection = 0

            idx = select_combo.findData(selection)
            if idx >= 0:
                select_combo.setCurrentIndex(idx)
            else:
                select_combo.setCurrentIndex(0)

            # Disable if there is no alternative to "Önerilen".
            select_combo.setEnabled(select_combo.count() > 1)
        finally:
            select_combo.blockSignals(False)

    def update_all_rune_select_combos(self) -> None:
        for role_key, combos in (self.role_rune_select_combos or {}).items():
            for i in range(min(3, len(combos))):
                self.update_rune_select_combo(role_key, i)

    def on_rune_selection_changed(self, role_key: str, index: int) -> None:
        combos = self.role_combos.get(role_key) or []
        if index >= len(combos):
            return

        champ_id = combos[index].currentData()
        if not champ_id:
            return

        select_combos = self.role_rune_select_combos.get(role_key) or []
        if index >= len(select_combos) or select_combos[index] is None:
            return

        try:
            selection_val = int(select_combos[index].currentData() or 0)
        except (TypeError, ValueError):
            selection_val = 0

        if selection_val not in (0, 1, 2, 3):
            selection_val = 0

        champ_key = str(champ_id)
        if selection_val == 0:
            # Keep config small; absence means "recommended".
            self.rune_selection.pop(champ_key, None)
        else:
            self.rune_selection[champ_key] = selection_val

        self.save_config()
        # Champion-based: reflect the same selection across all rows that use this champion.
        self.update_all_rune_select_combos()
        self.update_all_rune_buttons()

    def _save_rune_preset_for_champion(self, champ_id: int, slot: int, page: dict) -> None:
        champ_key = str(int(champ_id))
        slot_int = int(slot)
        if slot_int not in (1, 2, 3):
            return

        self.custom_runes.setdefault(champ_key, {})[str(slot_int)] = self._clone_rune_page(page)
        self.rune_selection[champ_key] = slot_int
        self.save_config()
        self.update_all_rune_buttons()
        self.update_all_rune_select_combos()

    def _delete_rune_preset_for_champion(self, champ_id: int, slot: int) -> None:
        champ_key = str(int(champ_id))
        slot_int = int(slot)
        if slot_int not in (1, 2, 3):
            return

        presets = self.custom_runes.get(champ_key)
        if isinstance(presets, dict):
            presets.pop(str(slot_int), None)
            if not presets:
                self.custom_runes.pop(champ_key, None)

        if self.rune_selection.get(champ_key) == slot_int:
            self.rune_selection.pop(champ_key, None)

        self.save_config()
        self.update_all_rune_buttons()
        self.update_all_rune_select_combos()

    def open_rune_presets_dialog(self, role_key: str, index: int) -> None:
        combos = self.role_combos.get(role_key) or []
        if index >= len(combos):
            return

        champ_combo = combos[index]
        champ_id = champ_combo.currentData()
        if not champ_id:
            QMessageBox.warning(self, "Eksik Seçim", "Önce şampiyon seçmelisiniz.")
            return

        try:
            champ_id_int = int(champ_id)
        except (TypeError, ValueError):
            QMessageBox.warning(self, "Geçersiz", "Geçersiz şampiyon ID.")
            return

        champ_name = champ_combo.currentText()
        champ_key = str(champ_id_int)
        presets = self.custom_runes.get(champ_key)
        presets = presets if isinstance(presets, dict) else {}

        initial_slot = 1
        try:
            sel = int(self.rune_selection.get(champ_key, 0) or 0)
        except (TypeError, ValueError):
            sel = 0
        if sel in (1, 2, 3) and isinstance(presets.get(str(sel)), dict):
            initial_slot = sel
        else:
            for s in (1, 2, 3):
                if isinstance(presets.get(str(s)), dict):
                    initial_slot = s
                    break

        dlg = RunePresetsDialog(
            champion_id=champ_id_int,
            champion_name=champ_name,
            existing_presets=presets,
            initial_slot=initial_slot,
            on_save_preset=lambda slot, page, cid=champ_id_int: self._save_rune_preset_for_champion(cid, slot, page),
            on_delete_preset=lambda slot, cid=champ_id_int: self._delete_rune_preset_for_champion(cid, slot),
            parent=self,
        )
        dlg.exec()

    def update_skin_button(self, role_key: str, index: int) -> None:
        buttons = self.role_skin_buttons.get(role_key) or []
        if index >= len(buttons) or buttons[index] is None:
            return
        button = buttons[index]

        combos = self.role_combos.get(role_key) or []
        if index >= len(combos):
            return
        champ_id = combos[index].currentData()

        if not champ_id:
            button.setText("Kostüm")
            button.setToolTip("Önce şampiyon seçin")
            button.setEnabled(False)
            self._set_button_configured(button, False)
            return

        button.setEnabled(True)
        cid = str(champ_id)
        role_skins = self.custom_skins.get(role_key) if isinstance(self.custom_skins, dict) else None
        role_skins = role_skins if isinstance(role_skins, dict) else {}
        has_custom = cid in role_skins
        self._set_button_configured(button, bool(has_custom))
        button.setText("Kostüm (Özel)" if has_custom else "Kostüm")
        button.setToolTip("Özel kostüm seçildi" if has_custom else "Varsayılan kostüm kullanılacak")

    def update_all_skin_buttons(self) -> None:
        for role_key, buttons in (self.role_skin_buttons or {}).items():
            for i in range(min(3, len(buttons))):
                self.update_skin_button(role_key, i)

    def _set_button_configured(self, button: QPushButton, configured: bool) -> None:
        """
        Qt stylesheet'in dinamik property tabanlı stillerini güncellemek için
        butona `configured=true/false` yazar ve stilin yeniden uygulanmasını sağlar.
        """
        try:
            current = button.property("configured")
            if isinstance(current, bool) and current == bool(configured):
                return
        except Exception:
            pass

        try:
            button.setProperty("configured", bool(configured))
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()
        except Exception:
            pass

    def _clone_rune_page(self, page: dict) -> dict:
        cloned = dict(page or {})
        perk_ids = cloned.get("selectedPerkIds")
        if isinstance(perk_ids, list):
            cloned["selectedPerkIds"] = list(perk_ids)
        return cloned

    def _find_custom_skin_any_role(self, champ_id: int) -> tuple[str, int] | None:
        cid = str(champ_id)
        for rk, skins in (self.custom_skins or {}).items():
            if not isinstance(skins, dict):
                continue
            val = skins.get(cid)
            if val is None:
                continue
            try:
                return rk, int(val)
            except (TypeError, ValueError):
                continue
        return None

    def _roles_where_champion_selected(self, champ_id: int) -> set[str]:
        roles: set[str] = set()
        for rk, combos in (self.role_combos or {}).items():
            for cb in combos:
                if cb.currentData() == champ_id:
                    roles.add(rk)
                    break
        return roles

    def on_champion_changed(self, role_key: str, index: int) -> None:
        combos = self.role_combos.get(role_key) or []
        if index >= len(combos):
            return

        champ_id = combos[index].currentData()
        if champ_id:
            role_skins = self.custom_skins.get(role_key) if isinstance(self.custom_skins, dict) else None
            role_skins = role_skins if isinstance(role_skins, dict) else {}

            # If this role doesn't have a custom skin yet but another role does,
            # copy it so the same champion behaves consistently across roles.
            if str(champ_id) not in role_skins:
                found_skin = self._find_custom_skin_any_role(champ_id)
                if found_skin is not None:
                    _src_role, skin_id = found_skin
                    self.custom_skins.setdefault(role_key, {})[str(champ_id)] = int(skin_id)

        self.update_champion_spell_row(role_key, index)
        self.update_all_rune_buttons()
        self.update_all_rune_select_combos()
        self.update_all_skin_buttons()

    def edit_custom_runes(self, role_key: str, index: int) -> None:
        # Backward-compatible entry point: open the preset menu.
        self.open_rune_presets_dialog(role_key, index)

    def _load_skin_options_for_champion(self, champ_id: int) -> list[tuple[int, str]]:
        """
        Seçili şampiyon için kostüm seçeneklerini döndürür.

        - Varsayılan (base) her zaman eklenir.
        - Ek olarak sadece sahip olunan kostümler listelenir.
        """
        champ_id_int = int(champ_id)
        base_skin_id = champ_id_int * 1000

        skin_name_by_id: dict[int, str] = {}
        champ_res = lcu_request("GET", f"/lol-game-data/assets/v1/champions/{champ_id_int}.json")
        if champ_res.status_code == 200:
            try:
                champ_json = champ_res.json()
            except Exception:
                champ_json = None
            skins = champ_json.get("skins") if isinstance(champ_json, dict) else None
            if isinstance(skins, list):
                for s in skins:
                    if not isinstance(s, dict):
                        continue
                    try:
                        sid = int(s.get("id"))
                    except (TypeError, ValueError):
                        continue
                    name = s.get("name")
                    if isinstance(name, str) and name.strip():
                        skin_name_by_id[sid] = name.strip()

        owned_skin_ids: set[int] = set()
        inv_res = lcu_request("GET", "/lol-inventory/v2/inventory/CHAMPION_SKIN")
        if inv_res.status_code == 200:
            try:
                inv = inv_res.json()
            except Exception:
                inv = None
            if isinstance(inv, list):
                lo = base_skin_id
                hi = base_skin_id + 1000
                for item in inv:
                    if not isinstance(item, dict):
                        continue
                    if item.get("owned") is not True:
                        continue
                    try:
                        sid = int(item.get("itemId"))
                    except (TypeError, ValueError):
                        continue
                    if lo <= sid < hi and sid != base_skin_id:
                        owned_skin_ids.add(sid)

        options: list[tuple[int, str]] = []

        base_name = skin_name_by_id.get(base_skin_id) or "Varsayılan"
        options.append((base_skin_id, f"Varsayılan ({base_name})"))

        for sid in sorted(owned_skin_ids):
            options.append((sid, skin_name_by_id.get(sid) or f"Kostüm {sid}"))

        return options

    def edit_custom_skin(self, role_key: str, index: int) -> None:
        combos = self.role_combos.get(role_key) or []
        if index >= len(combos):
            return

        combo = combos[index]
        champ_id = combo.currentData()
        if not champ_id:
            QMessageBox.warning(self, "Eksik Seçim", "Önce şampiyon seçmelisiniz.")
            return

        try:
            champ_id_int = int(champ_id)
        except (TypeError, ValueError):
            QMessageBox.warning(self, "Geçersiz", "Geçersiz şampiyon ID.")
            return

        base_skin_id = champ_id_int * 1000
        champ_name = combo.currentText()
        cid = str(champ_id_int)

        role_skins = self.custom_skins.get(role_key) if isinstance(self.custom_skins, dict) else None
        role_skins = role_skins if isinstance(role_skins, dict) else {}
        existing_role = role_skins.get(cid)

        existing_found = self._find_custom_skin_any_role(champ_id_int)
        baseline_skin_id = None
        if existing_role is not None:
            baseline_skin_id = existing_role
        elif existing_found is not None:
            baseline_skin_id = existing_found[1]

        try:
            selected_skin_id = int(baseline_skin_id) if baseline_skin_id is not None else base_skin_id
        except (TypeError, ValueError):
            selected_skin_id = base_skin_id

        try:
            options = self._load_skin_options_for_champion(champ_id_int)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kostüm listesi alınamadı:\n{e}")
            return

        dialog = SkinSelectDialog(
            champion_name=champ_name,
            skins=options,
            selected_skin_id=selected_skin_id,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_skin_id = dialog.get_selected_skin_id()
        if new_skin_id is None:
            return

        try:
            new_skin_id = int(new_skin_id)
        except (TypeError, ValueError):
            return

        if new_skin_id == base_skin_id:
            # Default seçildiyse tüm rollerden temizle.
            for rk in list((self.custom_skins or {}).keys()):
                skins = self.custom_skins.get(rk)
                if not isinstance(skins, dict):
                    continue
                skins.pop(cid, None)
                if not skins:
                    self.custom_skins.pop(rk, None)
        else:
            selected_roles = self._roles_where_champion_selected(champ_id_int)

            # Always save for the role the user edited.
            self.custom_skins.setdefault(role_key, {})[cid] = new_skin_id

            # Also update roles where the same champion is selected.
            for rk in selected_roles:
                if rk == role_key:
                    continue
                self.custom_skins.setdefault(rk, {})[cid] = new_skin_id

        self.save_config()
        self.update_all_skin_buttons()

    def stop_automation(self):
        if self._automation_action_inflight:
            return

        self._automation_action_inflight = True
        self._set_automation_ui_state("stopping")
        try:
            resp = requests.post(f"{API_BASE}/stop_automation", timeout=API_TIMEOUT_SEC)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")

            self._set_automation_ui_state("stopped")
            QMessageBox.information(self, "Durduruldu", f"{APP_DISPLAY_NAME} durduruldu.")
        except Exception as e:
            self._set_automation_ui_state("offline")
            QMessageBox.critical(self, "Hata", f"{APP_DISPLAY_NAME} durdurulamadı: {e}")
        finally:
            self._automation_action_inflight = False
            self._check_health_async()

    def closeEvent(self, event):
        try:
            self.save_config()
        except Exception as e:
            print(f"Config save error: {e}")
        super().closeEvent(event)

    def _build_automation_payload(self) -> dict:
        queue_name = self.queue_combo.currentText()
        queue_id = QUEUE_MODES.get(queue_name, 420)

        primary_role = ROLES.get(self.primary_role_combo.currentText())
        secondary_role = ROLES.get(self.secondary_role_combo.currentText())

        role_summoner_spells: dict[str, dict[str, int | None]] = {}
        for role_key in (self.role_combos or {}).keys():
            combos = self.role_combos.get(role_key) or []
            for i, champ_combo in enumerate(combos):
                if champ_combo.currentData() is None:
                    continue
                pair = self._get_champion_spell_pair(role_key, i)
                if pair is None:
                    continue
                spell1_combo, spell2_combo = pair
                role_summoner_spells[role_key] = {
                    "spell1Id": SUMMONER_SPELLS.get(spell1_combo.currentText()),
                    "spell2Id": SUMMONER_SPELLS.get(spell2_combo.currentText()),
                }
                break

        fallback_role_key = str(primary_role or "").upper()
        fallback_spells = role_summoner_spells.get(fallback_role_key) or {}
        spell1 = fallback_spells.get("spell1Id") if isinstance(fallback_spells, dict) else None
        spell2 = fallback_spells.get("spell2Id") if isinstance(fallback_spells, dict) else None

        role_champions: dict[str, list[int]] = {}
        for role_key, combos in self.role_combos.items():
            selected_ids: list[int] = []
            for cb in combos:
                val = cb.currentData()
                if val is None:
                    continue
                try:
                    selected_ids.append(int(val))
                except (TypeError, ValueError):
                    continue
            if selected_ids:
                role_champions[role_key] = selected_ids

        role_bans: dict[str, int] = {}
        for role_key, cb in self.role_ban_combos.items():
            val = cb.currentData()
            if val is None:
                continue
            try:
                role_bans[role_key] = int(val)
            except (TypeError, ValueError):
                continue

        custom_summoner_spells = self._sync_custom_summoner_spells_from_ui()

        return {
            "queue_id": int(queue_id),
            "primary_role": primary_role,
            "secondary_role": secondary_role,
            "primary_summoner_spell": spell1,
            "secondary_summoner_spell": spell2,
            "role_summoner_spells": role_summoner_spells,
            "custom_summoner_spells": custom_summoner_spells,
            "role_champions": role_champions,
            "role_bans": role_bans,
            "custom_runes": self.custom_runes,
            "rune_selection": self.rune_selection,
            "custom_skins": self.custom_skins,
        }

    def _schedule_live_config_push(self) -> None:
        if getattr(self, "_automation_state", "") != "running":
            return
        if getattr(self, "_automation_action_inflight", False):
            return

        timer = getattr(self, "_live_config_push_timer", None)
        if timer is None:
            self._live_config_push_timer = QTimer(self)
            self._live_config_push_timer.setSingleShot(True)
            self._live_config_push_timer.timeout.connect(self._push_live_config_to_api)
            timer = self._live_config_push_timer

        try:
            timer.start(350)
        except Exception:
            pass

    def _push_live_config_to_api(self) -> None:
        if getattr(self, "_automation_state", "") != "running":
            return
        if getattr(self, "_automation_action_inflight", False):
            return

        try:
            payload = self._build_automation_payload()
        except Exception as e:
            print(f"[CONFIG] Payload build failed: {e}")
            return

        def worker() -> None:
            try:
                resp = requests.post(
                    f"{API_BASE}/start_automation",
                    json=payload,
                    timeout=API_TIMEOUT_SEC,
                )
                if resp.status_code != 200:
                    print(f"[CONFIG] Live update failed: {resp.status_code} {resp.text}")
            except Exception as e:
                print(f"[CONFIG] Live update failed: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def start_automation(self):
        if self._automation_action_inflight:
            return

        try:
            # 1. Seçim doğrulama (tüm roller için)
            role_display = {v: k for k, v in ROLES.items() if v is not None}

            missing_lines: list[str] = []
            for role_key, combos in self.role_combos.items():
                display = role_display.get(role_key, role_key)
                ban_combo = self.role_ban_combos.get(role_key)
                ban_selected = ban_combo is not None and ban_combo.currentData() is not None
                champ_selected = any(cb.currentData() is not None for cb in combos)

                if not ban_selected and not champ_selected:
                    missing_lines.append(f"- {display}: ban ve şampiyon seçilmedi")
                elif not ban_selected:
                    missing_lines.append(f"- {display}: ban seçilmedi")
                elif not champ_selected:
                    missing_lines.append(f"- {display}: en az 1 şampiyon seçilmedi")

            if missing_lines:
                QMessageBox.warning(
                    self,
                    "Eksik Seçim",
                    f"{APP_DISPLAY_NAME} başlamadan önce tüm roller için ban ve en az 1 şampiyon seçmelisiniz:\n\n"
                    + "\n".join(missing_lines),
                )
                return

            self._automation_action_inflight = True
            self._set_automation_ui_state("starting")

            # API ayakta mı?
            try:
                health = requests.get(f"{API_BASE}/health", timeout=API_TIMEOUT_SEC)
                if health.status_code != 200:
                    raise RuntimeError(f"health status={health.status_code} body={health.text}")
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Sunucu Çalışmıyor",
                    f"FastAPI sunucusuna bağlanılamadı. Uygulamayı `run_app.py` / `{APP_DISPLAY_NAME}.exe` (eski: `LoLAutomation.exe`) ile başlattığınızdan emin olun.\n\n"
                    f"Detay: {e}",
                )
                self._set_automation_ui_state("offline")
                return

            payload = self._build_automation_payload()
            self.save_config()

            resp = requests.post(
                f"{API_BASE}/start_automation",
                json=payload,
                timeout=API_TIMEOUT_SEC,
            )
            if resp.status_code == 200:
                self._set_automation_ui_state("running")
                QMessageBox.information(self, "Başarılı", f"{APP_DISPLAY_NAME} başlatıldı!")
            else:
                self._set_automation_ui_state("offline")
                QMessageBox.critical(self, "Hata", f"API Hatası: {resp.status_code}\n\n{resp.text}")
        except Exception as e:
            import traceback

            self._set_automation_ui_state("offline")
            QMessageBox.critical(self, "Hata", f"Başlatılamadı:\n{e}\n\n{traceback.format_exc()}")
        finally:
            self._automation_action_inflight = False
            self._check_health_async()


    def load_config(self):
        config_path = CONFIG_FILE
        if not os.path.exists(config_path) and os.path.exists(LEGACY_APP_CONFIG_FILE):
            config_path = LEGACY_APP_CONFIG_FILE
        if not os.path.exists(config_path) and os.path.exists(LEGACY_CONFIG_FILE):
            config_path = LEGACY_CONFIG_FILE

        if not os.path.exists(config_path):
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Config load error: {e}")
            return

        raw_custom_runes = data.get("custom_runes", {}) or {}
        self.custom_runes = {}
        if isinstance(raw_custom_runes, dict):
            # Legacy format (role -> champId -> page) migration to:
            # champId -> slot("1") -> page
            legacy_role_keys = {"TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"}
            looks_legacy = any(str(k) in legacy_role_keys for k in raw_custom_runes.keys())
            if looks_legacy:
                migrated: dict[str, dict[str, dict]] = {}
                for _rk, pages in raw_custom_runes.items():
                    if not isinstance(pages, dict):
                        continue
                    for champ_key, page in pages.items():
                        try:
                            cid_int = int(champ_key)
                        except (TypeError, ValueError):
                            continue
                        if cid_int <= 0 or not isinstance(page, dict):
                            continue
                        migrated.setdefault(str(cid_int), {}).setdefault("1", page)
                self.custom_runes = migrated
            else:
                cleaned: dict[str, dict[str, dict]] = {}
                for champ_key, slots in raw_custom_runes.items():
                    try:
                        cid_int = int(champ_key)
                    except (TypeError, ValueError):
                        continue
                    if cid_int <= 0 or not isinstance(slots, dict):
                        continue
                    slot_map: dict[str, dict] = {}
                    for slot_key, page in slots.items():
                        sk = str(slot_key)
                        if sk not in ("1", "2", "3"):
                            continue
                        if isinstance(page, dict):
                            slot_map[sk] = page
                    if slot_map:
                        cleaned[str(cid_int)] = slot_map
                self.custom_runes = cleaned

        raw_selection = data.get("rune_selection", {}) or {}
        self.rune_selection = {}
        if isinstance(raw_selection, dict):
            for champ_key, sel in raw_selection.items():
                try:
                    cid_int = int(champ_key)
                    sel_int = int(sel)
                except (TypeError, ValueError):
                    continue
                if cid_int <= 0 or sel_int not in (1, 2, 3):
                    continue
                if str(cid_int) in self.custom_runes and str(sel_int) in (self.custom_runes.get(str(cid_int)) or {}):
                    self.rune_selection[str(cid_int)] = sel_int

        # If we just migrated legacy custom runes, keep old behavior by selecting preset 1.
        if "rune_selection" not in data and isinstance(raw_custom_runes, dict):
            legacy_role_keys = {"TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"}
            if any(str(k) in legacy_role_keys for k in raw_custom_runes.keys()):
                for champ_key in (self.custom_runes or {}).keys():
                    self.rune_selection.setdefault(str(champ_key), 1)
        self.custom_skins = data.get("custom_skins", {}) or {}
        if not isinstance(self.custom_skins, dict):
            self.custom_skins = {}
        self.custom_summoner_spells = data.get("custom_summoner_spells", {}) or {}
        if not isinstance(self.custom_summoner_spells, dict):
            self.custom_summoner_spells = {}

        # General Settings
        if "queue_name" in data:
            self.queue_combo.setCurrentText(data["queue_name"])

        # Role Bans
        # data["role_bans_ui"] format: { "TOP": banId, "JUNGLE": banId, ... }
        rb_ui = data.get("role_bans_ui", {})
        for role_key, cid in rb_ui.items():
            cb = self.role_ban_combos.get(role_key)
            if cb is not None:
                self.set_combo_by_data(cb, cid)

        if "primary_role_name" in data:
            self.primary_role_combo.setCurrentText(data["primary_role_name"])
        if "secondary_role_name" in data:
            self.secondary_role_combo.setCurrentText(data["secondary_role_name"])

        legacy_role_defaults: dict[str, tuple[int | None, int | None]] = {}
        legacy_role_defaults_present: set[str] = set()
        has_global_legacy = "spell1_name" in data or "spell2_name" in data
        global_legacy_s1: int | None = self._normalize_spell_id_from_any(data.get("spell1_name"))
        global_legacy_s2: int | None = self._normalize_spell_id_from_any(data.get("spell2_name"))
        role_spells_ui = data.get("role_spells_ui") or {}
        if isinstance(role_spells_ui, dict) and role_spells_ui:
            for role_key, spells in role_spells_ui.items():
                s1_val = None
                s2_val = None
                if isinstance(spells, dict):
                    s1_val = spells.get("spell1_name")
                    s2_val = spells.get("spell2_name")
                elif isinstance(spells, (list, tuple)) and len(spells) >= 2:
                    s1_val = spells[0]
                    s2_val = spells[1]
                role_key_str = str(role_key)
                legacy_role_defaults_present.add(role_key_str)
                legacy_role_defaults[role_key_str] = (
                    self._normalize_spell_id_from_any(s1_val),
                    self._normalize_spell_id_from_any(s2_val),
                )

        # Role Champions
        # data["role_champions_ui"] format: { "TOP": [id1, id2, id3], ... }
        rc_ui = data.get("role_champions_ui", {})
        for role_key, champ_ids in rc_ui.items():
            if role_key in self.role_combos:
                combos = self.role_combos[role_key]
                for i, cid in enumerate(champ_ids):
                    if i < len(combos):
                        combos[i].blockSignals(True)
                        try:
                            self.set_combo_by_data(combos[i], cid)
                        finally:
                            combos[i].blockSignals(False)

        # Migrate legacy role/global spells to champion-specific config if needed.
        for role_key, combos in (self.role_combos or {}).items():
            for i, cb in enumerate(combos):
                champ_id = cb.currentData()
                if not champ_id:
                    continue
                cid = str(champ_id)
                role_map = self.custom_summoner_spells.get(role_key)
                role_map = role_map if isinstance(role_map, dict) else {}
                if cid in role_map:
                    continue
                if role_key in legacy_role_defaults_present:
                    s1_id, s2_id = legacy_role_defaults.get(role_key, (None, None))
                elif has_global_legacy:
                    s1_id, s2_id = (global_legacy_s1, global_legacy_s2)
                else:
                    continue
                self.custom_summoner_spells.setdefault(role_key, {})[cid] = {
                    "spell1Id": s1_id,
                    "spell2Id": s2_id,
                }

        self.update_all_champion_spell_rows()
        self.update_all_rune_buttons()
        self.update_all_rune_select_combos()
        self.update_all_skin_buttons()

    def save_config(self):
        data = {}

        # General
        data["queue_name"] = self.queue_combo.currentText()

        data["primary_role_name"] = self.primary_role_combo.currentText()
        data["secondary_role_name"] = self.secondary_role_combo.currentText()

        self._sync_custom_summoner_spells_from_ui()
        data["custom_summoner_spells"] = self.custom_summoner_spells

        # Role Champions UI state
        # We save this specifically to restore the UI combo boxes exactly as they are
        rc_ui = {}
        for role_key, combos in self.role_combos.items():
            ids = []
            for cb in combos:
                ids.append(cb.currentData())
            rc_ui[role_key] = ids
        data["role_champions_ui"] = rc_ui

        # Role Bans UI state
        rb_ui = {}
        for role_key, cb in self.role_ban_combos.items():
            rb_ui[role_key] = cb.currentData()
        data["role_bans_ui"] = rb_ui

        data["custom_runes"] = self.custom_runes
        data["rune_selection"] = self.rune_selection
        data["custom_skins"] = self.custom_skins

        config_path = CONFIG_FILE
        try:
            config_dir = os.path.dirname(CONFIG_FILE)
            if config_dir:
                os.makedirs(config_dir, exist_ok=True)
        except Exception:
            try:
                legacy_dir = os.path.dirname(LEGACY_APP_CONFIG_FILE)
                if legacy_dir:
                    os.makedirs(legacy_dir, exist_ok=True)
                    config_path = LEGACY_APP_CONFIG_FILE
                else:
                    config_path = LEGACY_CONFIG_FILE
            except Exception:
                config_path = LEGACY_CONFIG_FILE

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Config save error: {e}")
        self._schedule_live_config_push()

    def _schedule_update_check(self) -> None:
        """
        Açılışta GitHub Releases üzerinden yeni sürüm var mı diye kontrol eder.

        Notlar:
        - Varsayılan repo: `UPDATE_REPO_DEFAULT` (ENV ile override edilebilir).
        - `RUNEPILOT_DISABLE_AUTO_UPDATE=1` ile tamamen kapatılabilir.
        """
        if self._update_check_started:
            return

        disable = (os.getenv("RUNEPILOT_DISABLE_AUTO_UPDATE") or "").strip().lower()
        if disable in ("1", "true", "yes", "on"):
            return

        repo = (os.getenv("RUNEPILOT_UPDATE_REPO") or UPDATE_REPO_DEFAULT or "").strip()
        if not repo:
            return

        self._update_check_started = True
        QTimer.singleShot(1500, self._check_updates_async)

    def _check_updates_async(self) -> None:
        repo = (os.getenv("RUNEPILOT_UPDATE_REPO") or UPDATE_REPO_DEFAULT or "").strip()
        if not repo:
            return
        token = (os.getenv("RUNEPILOT_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN") or "").strip() or None

        def worker() -> None:
            try:
                info = check_for_update(
                    current_version=__version__,
                    repo=repo,
                    token=token,
                    timeout_sec=4.0,
                )
            except Exception:
                info = None

            if info is not None:
                try:
                    self._update_emitter.update_available.emit(info)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_available(self, info_obj: object) -> None:
        try:
            info: UpdateInfo = info_obj  # type: ignore[assignment]
        except Exception:
            return

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("Güncelleme Mevcut")

        msg.setText(
            f"{APP_DISPLAY_NAME} için yeni sürüm bulundu.\n\n"
            f"Yüklü: {info.current_version}\n"
            f"Yeni: {info.latest_version}"
        )

        if info.release_notes:
            try:
                msg.setDetailedText(info.release_notes)
            except Exception:
                pass

        if info.asset_download_url:
            primary_btn = msg.addButton("Güncelle", QMessageBox.ButtonRole.AcceptRole)
        else:
            primary_btn = msg.addButton("Release Sayfasını Aç", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton("Daha Sonra", QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(primary_btn)

        msg.exec()
        if msg.clickedButton() != primary_btn:
            return

        if info.asset_download_url:
            self._start_update_download(info)
        else:
            self._safe_open_url(info.release_html_url)

    def _start_update_download(self, info: UpdateInfo) -> None:
        url = (info.asset_download_url or "").strip()
        if not url:
            self._safe_open_url(info.release_html_url)
            return

        token = (os.getenv("RUNEPILOT_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN") or "").strip() or None
        asset_name = (info.asset_name or f"RunePilotSetup-{info.latest_version}.exe").strip()
        dest_path = os.path.join(tempfile.gettempdir(), asset_name)

        try:
            dlg = QProgressDialog("Güncelleme indiriliyor...", None, 0, 0, self)
            dlg.setWindowTitle("Güncelleme")
            dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
            dlg.setCancelButton(None)
            dlg.setMinimumDuration(0)
            dlg.show()
            self._update_progress_dialog = dlg
        except Exception:
            self._update_progress_dialog = None

        def worker() -> None:
            ok, err = download_asset(url, dest_path, token=token, timeout_sec=300.0)
            try:
                self._update_emitter.download_finished.emit(bool(ok), str(dest_path), str(err or ""))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_download_finished(self, ok: bool, path: str, err: str) -> None:
        if self._update_progress_dialog is not None:
            try:
                self._update_progress_dialog.close()
            except Exception:
                pass
            self._update_progress_dialog = None

        if not ok:
            QMessageBox.critical(self, "Güncelleme", f"Güncelleme indirilemedi:\n\n{err or 'Bilinmeyen hata'}")
            return

        try:
            os.startfile(path)
        except Exception as e:
            QMessageBox.critical(self, "Güncelleme", f"Installer başlatılamadı:\n\n{e}")
            return

        try:
            QApplication.instance().quit()
        except Exception:
            pass

    def _safe_open_url(self, url: str | None) -> None:
        url = (url or "").strip()
        if not url:
            return
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def set_combo_by_data(self, combo: QComboBox, value):
        if value is None:
            combo.setCurrentIndex(0) # "Seçiniz" usually
            return
            
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def refresh_champions(self):
        self.save_config()
        self.load_champions()
        self.load_config()

    def load_champions(self):
        # Rol bazlı ban combolarını temizle
        for cb in self.role_ban_combos.values():
            cb.clear()
            cb.addItem("Yok", None)

        # Tüm rol combolarını temizle
        for combos in self.role_combos.values():
            for cb in combos:
                cb.clear()
                cb.addItem("Seçiniz", None)

        try:
            res = lcu_request("GET", "/lol-game-data/assets/v1/champion-summary.json")
            all_champs = res.json()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Şampiyon listesi alınamadı:\n{e}")
            return

        all_sorted = sorted(all_champs, key=lambda c: c.get("name", ""))

        for champ in all_sorted:
            try:
                cid = int(champ.get("id"))
            except (TypeError, ValueError):
                continue
            name = champ.get("name", champ.get("alias", str(cid)))
            
            for cb in self.role_ban_combos.values():
                cb.addItem(name, cid)

        # Pick: prefer owned / free-to-play champions to prevent pick errors
        pick_entries = {}
        try:
            res = lcu_request("GET", "/lol-champions/v1/owned-champions-minimal")
            owned_champs = res.json()
            if isinstance(owned_champs, list):
                for champ in owned_champs:
                    try:
                        cid = int(champ.get("id"))
                    except (TypeError, ValueError):
                        continue
                    if cid <= 0:
                        continue

                    ownership = champ.get("ownership", {})
                    owned = ownership.get("owned")
                    free_to_play = champ.get("freeToPlay")
                    if owned is False and not free_to_play:
                        continue

                    name = champ.get("name") or champ.get("alias") or str(cid)
                    pick_entries[cid] = name
        except Exception:
            pick_entries = {}

        # Fallback: if we can't read owned champs, keep previous behavior (show all)
        if not pick_entries:
            for champ in all_sorted:
                try:
                    cid = int(champ.get("id"))
                except (TypeError, ValueError):
                    continue
                name = champ.get("name", champ.get("alias", str(cid)))
                pick_entries[cid] = name

        for cid, name in sorted(pick_entries.items(), key=lambda x: x[1]):
            for combos in self.role_combos.values():
                for cb in combos:
                    cb.addItem(name, cid)

        self.update_all_rune_buttons()
        self.update_all_rune_select_combos()
        self.update_all_skin_buttons()

    def check_game_phase(self):
        """
        LCU gameflow fazını izler.
        GameStart veya InProgress olduğunda bir kere bildirim atar.
        """
        try:
            res = lcu_request("GET", "/lol-gameflow/v1/gameflow-phase")
            phase = res.json()
        except Exception:
            return

        if phase != self.last_phase:
            print(f"[GAMEFLOW] phase={phase}")
            self.last_phase = phase

            if phase in ("GameStart", "InProgress"):
                self.toaster.show_toast(
                    APP_DISPLAY_NAME,
                    "Oyun başladı! Seçimler uygulandı.",
                    duration=5,
                    threaded=True,
                )


# -----------------------------------------------------------------------------
# STYLING (HEXTECH DARK THEME)
# -----------------------------------------------------------------------------
STYLESHEET = """
QWidget {
    background-color: #010a13;
    color: #cdbe91;
    font-family: 'Segoe UI', sans-serif;
    font-size: 14px;
}

QLabel#appTitle {
    color: #f0e6d2;
    font-size: 22px;
    font-weight: 800;
    padding: 6px 0;
}

QLabel#appSubtitle {
    color: #a09b8c;
    font-size: 12px;
    padding-bottom: 8px;
}

QLabel#cornerStatusLabel {
    padding: 4px 10px;
    border-radius: 12px;
    font-weight: 700;
    border: 1px solid #3c3c3c;
    background-color: #1e282d;
    color: #f0e6d2;
    font-size: 12px;
}

QLabel#cornerStatusLabel[state="running"] {
    background-color: #1aa865;
    border-color: #1aa865;
    color: #010a13;
}

QLabel#cornerStatusLabel[state="stopped"] {
    background-color: #111821;
    border-color: #2b2f36;
    color: #f0e6d2;
}

QLabel#cornerStatusLabel[state="offline"] {
    background-color: #d64545;
    border-color: #d64545;
    color: #010a13;
}

QLabel#cornerStatusLabel[state="checking"],
QLabel#cornerStatusLabel[state="starting"] {
    background-color: #c8aa6e;
    border-color: #c8aa6e;
    color: #010a13;
}

QLabel#cornerStatusLabel[state="stopping"] {
    background-color: #d64545;
    border-color: #d64545;
    color: #010a13;
}

QProgressBar#cornerProgress {
    background-color: #111821;
    border: 1px solid #2b2f36;
    border-radius: 5px;
}

QProgressBar#cornerProgress::chunk {
    background-color: #c8aa6e;
    border-radius: 4px;
}

QProgressBar#cornerProgress[state="running"]::chunk {
    background-color: #1aa865;
}

QProgressBar#cornerProgress[state="offline"]::chunk,
QProgressBar#cornerProgress[state="stopping"]::chunk {
    background-color: #d64545;
}

QLabel#automationStatus {
    padding: 6px 12px;
    border-radius: 16px;
    font-weight: 700;
    border: 1px solid #3c3c3c;
    background-color: #1e282d;
    color: #f0e6d2;
    min-width: 190px;
}

QLabel#automationStatus[state="running"] {
    background-color: #1aa865;
    border-color: #1aa865;
    color: #010a13;
}

QLabel#automationStatus[state="stopped"] {
    background-color: #111821;
    border-color: #2b2f36;
    color: #f0e6d2;
}

QLabel#automationStatus[state="offline"] {
    background-color: #d64545;
    border-color: #d64545;
    color: #010a13;
}

QLabel#automationStatus[state="checking"],
QLabel#automationStatus[state="starting"] {
    background-color: #c8aa6e;
    border-color: #c8aa6e;
    color: #010a13;
}

QLabel#automationStatus[state="stopping"] {
    background-color: #d64545;
    border-color: #d64545;
    color: #010a13;
}

QGroupBox {
    border: 1px solid #c8aa6e;
    border-radius: 4px;
    margin-top: 20px;
    font-weight: bold;
    color: #f0e6d2;
    background-color: rgba(30, 40, 45, 120);
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 0 10px;
    color: #c8aa6e;
}

QLabel {
    color: #a09b8c;
}

QComboBox {
    background-color: #1e282d;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    padding: 4px;
    color: #f0e6d2;
    min-height: 20px;
}

QComboBox:hover {
    border: 1px solid #c8aa6e;
}

QComboBox:focus {
    border: 1px solid #c8aa6e;
}

QComboBox QAbstractItemView {
    background-color: #0b151f;
    border: 1px solid #3c3c3c;
    selection-background-color: #c8aa6e;
    selection-color: #010a13;
    padding: 4px;
    outline: 0;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left-width: 0px;
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
}

QTabWidget::pane {
    border: 1px solid #3c3c3c;
    background-color: #010a13;
}

QTabBar::tab {
    background: #1e282d;
    border: 1px solid #3c3c3c;
    color: #a09b8c;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:hover {
    border: 1px solid #c8aa6e;
    color: #f0e6d2;
}

QTabBar::tab:selected {
    background: #010a13;
    border-color: #c8aa6e;
    border-bottom-color: #010a13;
    color: #f0e6d2;
    font-weight: bold;
}

QPushButton {
    background-color: #0f1923;
    border: 1px solid #3c3c3c;
    color: #f0e6d2;
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 14px;
}

QPushButton:hover {
    background-color: #1e282d;
    border-color: #c8aa6e;
}

QPushButton:pressed {
    background-color: #0b121a;
}

QPushButton:disabled {
    background-color: #111821;
    border: 1px solid #2b2f36;
    color: #6b7280;
}

QPushButton#refreshButton {
    border-color: #c8aa6e;
    color: #c8aa6e;
}

QPushButton#refreshButton:hover {
    background-color: #1e282d;
    border-color: #f0e6d2;
    color: #f0e6d2;
}

QPushButton#runeButton[configured="true"],
QPushButton#skinButton[configured="true"] {
    background-color: #c8aa6e;
    border-color: #c8aa6e;
    color: #010a13;
}

QPushButton#runeButton[configured="true"]:hover,
QPushButton#skinButton[configured="true"]:hover {
    background-color: #f0e6d2;
    border-color: #f0e6d2;
    color: #010a13;
}

QPushButton#startButton {
    background-color: #1aa865;
    border-color: #1aa865;
    color: #010a13;
}

QPushButton#startButton:hover {
    background-color: #22c172;
    border-color: #1aa865;
    color: #010a13;
}

QPushButton#startButton:pressed {
    background-color: #12804c;
    border-color: #f0e6d2;
    color: #f0e6d2;
}

QPushButton#startButton:disabled,
QPushButton#startButton[automationState="running"]:disabled,
QPushButton#startButton[automationState="stopping"]:disabled {
    background-color: #1aa865;
    border-color: #1aa865;
    color: #010a13;
}

QPushButton#startButton[automationState="starting"]:disabled {
    background-color: #c8aa6e;
    border-color: #c8aa6e;
    color: #010a13;
}

QPushButton#stopButton {
    background-color: #d64545;
    border-color: #d64545;
    color: #010a13;
}

QPushButton#stopButton:hover {
    background-color: #e25a5a;
    border-color: #d64545;
    color: #010a13;
}

QPushButton#stopButton:pressed {
    background-color: #9e3030;
    border-color: #f0e6d2;
    color: #f0e6d2;
}

QPushButton#stopButton[automationState="stopping"]:disabled {
    background-color: #d64545;
    border-color: #d64545;
    color: #010a13;
}
"""


def main() -> None:
    """Masaüstü uygulamasını başlatır (Qt event loop)."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Optional: base style
    app.setStyleSheet(STYLESHEET)
    try:
        app.setApplicationDisplayName(APP_DISPLAY_NAME)
        app.setApplicationName(APP_ID)
        app.setApplicationVersion(__version__)
        app.setWindowIcon(QIcon(resource_path("assets/app_icon.png")))
    except Exception:
        pass
    
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
