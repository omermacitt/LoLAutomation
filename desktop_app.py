"""
RunePilot masaüstü uygulaması (PyQt6).

Kullanıcıdan rol/ban/şampiyon tercihlerini alır, `api.py` üzerindeki FastAPI
servisine gönderir ve otomasyonu kontrol eder.
"""
import sys
import os
import json
import requests

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
)
from PyQt6.QtCore import Qt, QTimer, QObject, QEvent

from win10toast import ToastNotifier

from lcu import lcu_request  # mevcut projenizdeki lcu.py'den
from runes_dialog import RunePageDialog

API_BASE = "http://127.0.0.1:8000"  # FastAPI sunucunun adresi
API_TIMEOUT_SEC = 3
APP_DISPLAY_NAME = "RunePilot"
APP_ID = "RunePilot"
LEGACY_APP_ID = "LoLAutomation"
LEGACY_CONFIG_FILE = "user_config.json"

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
    "Tüket (Smite)": 11,
    "Bitkinlik (Exhaust)": 3,
    "Kalkan (Barrier)": 21,
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
        # role -> [ (spell1_combo, spell2_combo), ... ] (champion rows)
        self.role_champion_spell_combos = {}
        # role -> champId(str) -> rune page dict
        self.custom_runes = {}
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
        
        self.start_button = QPushButton("Başlat")
        self.start_button.setObjectName("startButton")
        self.start_button.clicked.connect(self.start_automation)
        self.start_button.setFixedHeight(40)
        button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Durdur")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.clicked.connect(self.stop_automation)
        self.stop_button.setFixedHeight(40)
        self.stop_button.setEnabled(False) # Başlangıçta pasif
        button_layout.addWidget(self.stop_button)

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
            return "Sıçra (Flash)", "Tüket (Smite)"
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
            spell2_combo.setCurrentText("Tüket (Smite)")
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

        button = QPushButton("Rünler")
        button.setFixedWidth(95)
        button.clicked.connect(lambda _=False, rk=role_key, i=index: self.edit_custom_runes(rk, i))
        row_layout.addWidget(button)

        self.role_rune_buttons.setdefault(role_key, [None, None, None])
        self.role_rune_buttons[role_key][index] = button

        combo.currentIndexChanged.connect(lambda _=0, rk=role_key, i=index: self.on_champion_changed(rk, i))
        self.update_rune_button(role_key, index)
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
            return

        button.setEnabled(True)
        has_custom = str(champ_id) in (self.custom_runes.get(role_key) or {})
        button.setText("Rünler (Özel)" if has_custom else "Rünler")
        button.setToolTip("Özel rün kaydedildi" if has_custom else "Önerilen rün kullanılacak")

    def update_all_rune_buttons(self) -> None:
        for role_key, buttons in (self.role_rune_buttons or {}).items():
            for i in range(min(3, len(buttons))):
                self.update_rune_button(role_key, i)

    def _clone_rune_page(self, page: dict) -> dict:
        cloned = dict(page or {})
        perk_ids = cloned.get("selectedPerkIds")
        if isinstance(perk_ids, list):
            cloned["selectedPerkIds"] = list(perk_ids)
        return cloned

    def _find_custom_page_any_role(self, champ_id: int) -> tuple[str, dict] | None:
        cid = str(champ_id)
        for rk, pages in (self.custom_runes or {}).items():
            if not isinstance(pages, dict):
                continue
            page = pages.get(cid)
            if isinstance(page, dict):
                return rk, page
        return None

    def _roles_where_champion_selected(self, champ_id: int) -> set[str]:
        roles: set[str] = set()
        for rk, combos in (self.role_combos or {}).items():
            for cb in combos:
                if cb.currentData() == champ_id:
                    roles.add(rk)
                    break
        return roles

    def _rune_page_equal(self, a: dict | None, b: dict | None) -> bool:
        if a is None or b is None:
            return False
        try:
            return (
                str(a.get("name") or "") == str(b.get("name") or "")
                and int(a.get("primaryStyleId")) == int(b.get("primaryStyleId"))
                and int(a.get("subStyleId")) == int(b.get("subStyleId"))
                and list(a.get("selectedPerkIds") or []) == list(b.get("selectedPerkIds") or [])
            )
        except Exception:
            return a == b

    def on_champion_changed(self, role_key: str, index: int) -> None:
        combos = self.role_combos.get(role_key) or []
        if index >= len(combos):
            return

        champ_id = combos[index].currentData()
        if champ_id:
            role_pages = self.custom_runes.get(role_key) if isinstance(self.custom_runes, dict) else None
            role_pages = role_pages if isinstance(role_pages, dict) else {}

            # If this role doesn't have a custom page yet but another role does,
            # copy it so the same champion behaves consistently across roles.
            if str(champ_id) not in role_pages:
                found = self._find_custom_page_any_role(champ_id)
                if found is not None:
                    _src_role, page = found
                    self.custom_runes.setdefault(role_key, {})[str(champ_id)] = self._clone_rune_page(page)

        self.update_champion_spell_row(role_key, index)
        self.update_all_rune_buttons()

    def edit_custom_runes(self, role_key: str, index: int) -> None:
        combos = self.role_combos.get(role_key) or []
        if index >= len(combos):
            return

        combo = combos[index]
        champ_id = combo.currentData()
        if not champ_id:
            QMessageBox.warning(self, "Eksik Seçim", "Önce şampiyon seçmelisiniz.")
            return

        champ_name = combo.currentText()

        cid = str(champ_id)
        role_pages = self.custom_runes.get(role_key) if isinstance(self.custom_runes, dict) else None
        role_pages = role_pages if isinstance(role_pages, dict) else {}
        existing_page_role = role_pages.get(cid) if isinstance(role_pages.get(cid), dict) else None
        existing_found = self._find_custom_page_any_role(champ_id)
        baseline_page = existing_page_role or (existing_found[1] if existing_found else None)

        dialog = RunePageDialog(champion_name=champ_name, existing_page=baseline_page, parent=self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if dialog.action == "delete":
            # Remove pages that are effectively "the same" baseline across roles to
            # keep the champion consistent when it is used in multiple roles.
            for rk in list((self.custom_runes or {}).keys()):
                pages = self.custom_runes.get(rk)
                if not isinstance(pages, dict):
                    continue
                page = pages.get(cid)
                if baseline_page is not None and not self._rune_page_equal(page, baseline_page):
                    continue
                pages.pop(cid, None)
                if not pages:
                    self.custom_runes.pop(rk, None)
        else:
            page = dialog.get_rune_page(allow_incomplete=False)
            if not page:
                return

            new_page = self._clone_rune_page(page)
            selected_roles = self._roles_where_champion_selected(champ_id)

            # Always save for the role the user edited.
            self.custom_runes.setdefault(role_key, {})[cid] = self._clone_rune_page(new_page)

            # Also update any roles that previously shared the same baseline page,
            # and create entries for roles where the same champion is selected.
            for rk in set(list((self.custom_runes or {}).keys()) + list(selected_roles)):
                if rk == role_key:
                    continue
                pages = self.custom_runes.get(rk)
                pages = pages if isinstance(pages, dict) else {}
                existing = pages.get(cid) if isinstance(pages.get(cid), dict) else None

                if existing is None:
                    if rk in selected_roles:
                        self.custom_runes.setdefault(rk, {})[cid] = self._clone_rune_page(new_page)
                    continue

                if baseline_page is not None and self._rune_page_equal(existing, baseline_page):
                    self.custom_runes.setdefault(rk, {})[cid] = self._clone_rune_page(new_page)

        self.save_config()
        self.update_all_rune_buttons()

    def stop_automation(self):
        try:
            requests.post(f"{API_BASE}/stop_automation", timeout=API_TIMEOUT_SEC)
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.start_button.setText("Başlat")
            QMessageBox.information(self, "Durduruldu", f"{APP_DISPLAY_NAME} durduruldu.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"{APP_DISPLAY_NAME} durdurulamadı: {e}")

    def closeEvent(self, event):
        try:
            self.save_config()
        except Exception as e:
            print(f"Config save error: {e}")
        super().closeEvent(event)

    def start_automation(self):
        try:
            # 1. Verileri topla
            queue_name = self.queue_combo.currentText()
            queue_id = QUEUE_MODES.get(queue_name, 420)

            primary_role_name = self.primary_role_combo.currentText()
            primary_role = ROLES.get(primary_role_name)

            secondary_role_name = self.secondary_role_combo.currentText()
            secondary_role = ROLES.get(secondary_role_name)

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

            # 2. Seçim doğrulama (tüm roller için)
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

            role_champions = {}
            for role_key, combos in self.role_combos.items():
                selected_ids = []
                for cb in combos:
                    val = cb.currentData()
                    if val is not None:
                        selected_ids.append(val)
                if selected_ids:
                    role_champions[role_key] = selected_ids

            role_bans = {}
            for role_key, cb in self.role_ban_combos.items():
                val = cb.currentData()
                if val is not None:
                    role_bans[role_key] = val

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
                return

            # Ayarları kaydet
            custom_summoner_spells = self._sync_custom_summoner_spells_from_ui()
            self.save_config()

            payload = {
                "queue_id": queue_id,
                "primary_role": primary_role,
                "secondary_role": secondary_role,
                "primary_summoner_spell": spell1,
                "secondary_summoner_spell": spell2,
                "role_summoner_spells": role_summoner_spells,
                "custom_summoner_spells": custom_summoner_spells,
                "role_champions": role_champions,
                "role_bans": role_bans,
                "custom_runes": self.custom_runes,
            }

            resp = requests.post(
                f"{API_BASE}/start_automation",
                json=payload,
                timeout=API_TIMEOUT_SEC,
            )
            if resp.status_code == 200:
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(True)
                self.start_button.setText("Çalışıyor")
                QMessageBox.information(self, "Başarılı", f"{APP_DISPLAY_NAME} başlatıldı!")
            else:
                QMessageBox.critical(self, "Hata", f"API Hatası: {resp.status_code}\n\n{resp.text}")
        except Exception as e:
            import traceback

            QMessageBox.critical(self, "Hata", f"Başlatılamadı:\n{e}\n\n{traceback.format_exc()}")


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

        self.custom_runes = data.get("custom_runes", {}) or {}
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
    color: #2b2f36;
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

QPushButton#startButton {
    border-color: #1aa865;
    color: #1aa865;
}

QPushButton#startButton:hover {
    background-color: #1aa865;
    border-color: #1aa865;
    color: #010a13;
}

QPushButton#startButton:pressed {
    background-color: #12804c;
    border-color: #f0e6d2;
    color: #f0e6d2;
}

QPushButton#stopButton {
    border-color: #d64545;
    color: #d64545;
}

QPushButton#stopButton:hover {
    background-color: #d64545;
    border-color: #d64545;
    color: #010a13;
}

QPushButton#stopButton:pressed {
    background-color: #9e3030;
    border-color: #f0e6d2;
    color: #f0e6d2;
}
"""


def main() -> None:
    """Masaüstü uygulamasını başlatır (Qt event loop)."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Optional: base style
    app.setStyleSheet(STYLESHEET)
    try:
        app.setApplicationDisplayName(APP_DISPLAY_NAME)
        app.setWindowIcon(QIcon(resource_path("assets/app_icon.png")))
    except Exception:
        pass
    
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
