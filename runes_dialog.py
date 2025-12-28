"""
Özel rün sayfası düzenleme diyaloğu (PyQt6).

League Client (LCU) üzerinden rune style/perk verisini çekip kullanıcıya seçim
arayüzü sunar ve seçilen rünleri API'ye gönderilebilecek formatta üretir.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from lcu import lcu_request

MAIN_STYLE_IDS: set[int] = {8000, 8100, 8200, 8300, 8400}
STAT_MODS_STYLE_ID = 5000
DEFAULT_ICON_SIZE = QSize(24, 24)

# Cache perk/style data per process to avoid repeated LCU calls.
_PERK_STYLES_CACHE: list[dict[str, Any]] | None = None
_PERKS_CACHE: list[dict[str, Any]] | None = None


def _safe_int(value: Any) -> int | None:
    """Değeri int'e çevirmeyi dener; mümkün değilse `None` döndürür."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_rune_id_and_name(rune: Any) -> tuple[int, str] | None:
    """Perk/rune objesinden (id, name) ikilisini çıkartır."""
    return _extract_rune_id_and_name_with_lookup(rune, None)


def _extract_rune_id_and_name_with_lookup(
    rune: Any, perk_names: dict[int, str] | None
) -> tuple[int, str] | None:
    """Farklı veri formatlarını destekleyerek (id, name) çözümlemesi yapar."""
    if isinstance(rune, dict):
        rid = _safe_int(rune.get("id") or rune.get("perkId") or rune.get("runeId"))
        if rid is None:
            return None
        name = (
            rune.get("name")
            or rune.get("displayName")
            or rune.get("perkName")
            or (perk_names.get(rid) if perk_names else None)
            or str(rid)
        )
        return rid, str(name)

    rid = _safe_int(rune)
    if rid is None:
        return None
    resolved = (perk_names.get(rid) if perk_names else None) or rid
    return rid, str(resolved)


def _get_slot_runes(slot: Any) -> list[Any]:
    """LCU slot objesinden rune listesine güvenli erişim sağlar."""
    if not isinstance(slot, dict):
        return []
    runes = slot.get("runes")
    if runes is None:
        runes = slot.get("perks")
    if runes is None:
        runes = slot.get("perkIds")
    if runes is None:
        runes = slot.get("runeIds")
    return runes if isinstance(runes, list) else []


def _fetch_perk_styles() -> list[dict[str, Any]]:
    """LCU üzerinden rune style listesini okur."""
    global _PERK_STYLES_CACHE
    if _PERK_STYLES_CACHE is not None:
        return _PERK_STYLES_CACHE
    res = lcu_request("GET", "/lol-perks/v1/styles")
    res.raise_for_status()
    data = res.json()
    if not isinstance(data, list):
        raise ValueError("Unexpected response from /lol-perks/v1/styles")
    _PERK_STYLES_CACHE = data
    return data


def _fetch_perks() -> list[dict[str, Any]]:
    """LCU üzerinden perk listesini okur (farklı endpoint'lere fallback)."""
    global _PERKS_CACHE
    if _PERKS_CACHE is not None:
        return _PERKS_CACHE
    endpoints = (
        "/lol-perks/v1/perks",
        "/lol-game-data/assets/v1/perks.json",
    )
    last_error: Exception | None = None
    for endpoint in endpoints:
        try:
            res = lcu_request("GET", endpoint)
            res.raise_for_status()
            data = res.json()
            if isinstance(data, list):
                _PERKS_CACHE = data
                return data
            if isinstance(data, dict) and isinstance(data.get("perks"), list):
                _PERKS_CACHE = data["perks"]
                return data["perks"]
            last_error = ValueError(f"Unexpected response from {endpoint}")
        except Exception as e:
            last_error = e
            continue
    raise ValueError("Could not fetch perks") from last_error


def _normalize_asset_path(icon_path: str | None) -> str | None:
    """LCU ikon yolunu normalize eder; remote URL'leri devre dışı bırakır."""
    if not icon_path:
        return None
    path = str(icon_path).strip()
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return None
    if path.startswith("/"):
        return path
    return "/lol-game-data/assets/v1/" + path.lstrip("/")


def _get_style_slots(style: dict[str, Any]) -> list[Any]:
    """Style objesinden slot listesini güvenli şekilde okur."""
    slots = style.get("slots")
    if slots is None:
        slots = style.get("perkSlots")
    if slots is None:
        slots = style.get("runeSlots")
    return slots if isinstance(slots, list) else []


class RunePageDialog(QDialog):
    """Kullanıcının özel rün sayfası oluşturmasını/düzenlemesini sağlayan diyalog."""
    def __init__(
        self,
        *,
        champion_name: str,
        existing_page: dict[str, Any] | None = None,
        show_buttons: bool = True,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._show_buttons = bool(show_buttons)
        self.setWindowTitle(f"Custom Runes - {champion_name}")
        self.setMinimumWidth(520)

        self.action: str = "save"  # "save" | "delete"
        self._styles: dict[int, dict[str, Any]] = {}
        self._perk_names: dict[int, str] = {}
        self._perk_icon_paths: dict[int, str] = {}
        self._perk_icons: dict[int, QIcon | None] = {}
        self._secondary_last_changed: int | None = None

        self.name_edit = QLineEdit()
        self.primary_style_combo = QComboBox()
        self.secondary_style_combo = QComboBox()

        self.primary_rune_combos: list[QComboBox] = [QComboBox() for _ in range(4)]
        self.secondary_rune_combos: list[QComboBox] = [QComboBox() for _ in range(2)]
        self.shard_combos: list[QComboBox] = [QComboBox() for _ in range(3)]

        self.summary_label = QLabel("")

        try:
            styles_list = _fetch_perk_styles()
            self._styles = {
                int(s["id"]): s for s in styles_list if isinstance(s, dict) and _safe_int(s.get("id")) is not None
            }
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load rune styles from League Client:\n{e}")
            self._styles = {}

        try:
            perks_list = _fetch_perks()
            self._perk_names = {
                int(p["id"]): str(p.get("name") or p.get("displayName") or p["id"])
                for p in perks_list
                if isinstance(p, dict) and _safe_int(p.get("id")) is not None
            }
            self._perk_icon_paths = {
                int(p["id"]): str(p.get("iconPath") or p.get("icon_path") or "")
                for p in perks_list
                if isinstance(p, dict) and _safe_int(p.get("id")) is not None
            }
        except Exception:
            self._perk_names = {}
            self._perk_icon_paths = {}

        for cb in self.primary_rune_combos + self.secondary_rune_combos + self.shard_combos:
            cb.setIconSize(DEFAULT_ICON_SIZE)

        self._build_ui()
        self._wire_signals()
        self._populate_style_combos()

        if existing_page:
            self._apply_existing_page(existing_page, fallback_name=f"Custom-{champion_name}")
        else:
            self.name_edit.setText(f"Custom-{champion_name}")

        self._refresh_all()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        header = QGroupBox("Rune Page")
        header_layout = QFormLayout(header)
        header_layout.addRow("Name:", self.name_edit)
        header_layout.addRow("Primary Path:", self.primary_style_combo)
        header_layout.addRow("Secondary Path:", self.secondary_style_combo)
        root.addWidget(header)

        primary_group = QGroupBox("Primary Runes")
        primary_layout = QFormLayout(primary_group)
        primary_layout.addRow("Keystone:", self.primary_rune_combos[0])
        primary_layout.addRow("Slot 1:", self.primary_rune_combos[1])
        primary_layout.addRow("Slot 2:", self.primary_rune_combos[2])
        primary_layout.addRow("Slot 3:", self.primary_rune_combos[3])
        root.addWidget(primary_group)

        secondary_group = QGroupBox("Secondary Runes")
        secondary_layout = QFormLayout(secondary_group)
        secondary_layout.addRow("Secondary 1:", self.secondary_rune_combos[0])
        secondary_layout.addRow("Secondary 2:", self.secondary_rune_combos[1])
        root.addWidget(secondary_group)

        shards_group = QGroupBox("Shards")
        shards_layout = QFormLayout(shards_group)
        shards_layout.addRow("Shard 1:", self.shard_combos[0])
        shards_layout.addRow("Shard 2:", self.shard_combos[1])
        shards_layout.addRow("Shard 3:", self.shard_combos[2])
        root.addWidget(shards_group)

        root.addWidget(self.summary_label)

        if self._show_buttons:
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
            self._delete_button = buttons.addButton("Remove Custom", QDialogButtonBox.ButtonRole.DestructiveRole)
            buttons.accepted.connect(self._on_save)
            buttons.rejected.connect(self.reject)
            self._delete_button.clicked.connect(self._on_delete)

            buttons_row = QHBoxLayout()
            buttons_row.addWidget(buttons)
            root.addLayout(buttons_row)

    def _wire_signals(self) -> None:
        self.primary_style_combo.currentIndexChanged.connect(self._refresh_all)
        self.secondary_style_combo.currentIndexChanged.connect(self._refresh_secondary_only)
        for cb in self.primary_rune_combos + self.secondary_rune_combos + self.shard_combos:
            cb.currentIndexChanged.connect(self._refresh_summary)
        for idx, cb in enumerate(self.secondary_rune_combos):
            cb.currentIndexChanged.connect(lambda _=0, i=idx: self._on_secondary_changed(i))

    def _populate_style_combos(self) -> None:
        self.primary_style_combo.blockSignals(True)
        self.primary_style_combo.clear()

        main_styles = [s for sid, s in self._styles.items() if sid in MAIN_STYLE_IDS]
        main_styles.sort(key=lambda s: str(s.get("name") or ""))
        for s in main_styles:
            self.primary_style_combo.addItem(str(s.get("name") or s.get("id")), int(s["id"]))

        if self.primary_style_combo.count() > 0 and self.primary_style_combo.currentIndex() < 0:
            self.primary_style_combo.setCurrentIndex(0)
        self.primary_style_combo.blockSignals(False)

        self._rebuild_secondary_style_items()

    def _get_perk_icon(self, perk_id: Any) -> QIcon | None:
        pid = _safe_int(perk_id)
        if pid is None:
            return None
        if pid in self._perk_icons:
            return self._perk_icons[pid]

        icon_path = self._perk_icon_paths.get(pid)
        asset_path = _normalize_asset_path(icon_path)
        if asset_path is None:
            self._perk_icons[pid] = None
            return None

        try:
            res = lcu_request("GET", asset_path)
            if res.status_code != 200:
                self._perk_icons[pid] = None
                return None
            pixmap = QPixmap()
            if not pixmap.loadFromData(res.content):
                self._perk_icons[pid] = None
                return None
            icon = QIcon(pixmap)
            self._perk_icons[pid] = icon
            return icon
        except Exception:
            self._perk_icons[pid] = None
            return None

    def _rebuild_secondary_style_items(self) -> None:
        selected_primary = self.primary_style_combo.currentData()
        selected_primary_id = _safe_int(selected_primary)

        prev_secondary_id = _safe_int(self.secondary_style_combo.currentData())
        self.secondary_style_combo.blockSignals(True)
        self.secondary_style_combo.clear()

        main_styles = [s for sid, s in self._styles.items() if sid in MAIN_STYLE_IDS and sid != selected_primary_id]
        main_styles.sort(key=lambda s: str(s.get("name") or ""))
        for s in main_styles:
            self.secondary_style_combo.addItem(str(s.get("name") or s.get("id")), int(s["id"]))

        if prev_secondary_id is not None:
            idx = self.secondary_style_combo.findData(prev_secondary_id)
            if idx >= 0:
                self.secondary_style_combo.setCurrentIndex(idx)
        if self.secondary_style_combo.count() > 0 and self.secondary_style_combo.currentIndex() < 0:
            self.secondary_style_combo.setCurrentIndex(0)
        self.secondary_style_combo.blockSignals(False)

    def _refresh_all(self) -> None:
        self._rebuild_secondary_style_items()
        self._refresh_primary_only()
        self._refresh_secondary_only()
        self._refresh_shards()
        self._refresh_summary()

    def _get_secondary_slot_from_data(self, data: Any) -> int | None:
        if isinstance(data, dict):
            return _safe_int(data.get("slot"))
        return None

    def _infer_secondary_slot(self, style_id: int, rune_id: int) -> int | None:
        style = self._styles.get(style_id)
        if not style:
            return None
        slots = _get_style_slots(style)
        for slot_idx in range(1, min(4, len(slots))):
            slot = slots[slot_idx]
            for r in _get_slot_runes(slot):
                extracted = _extract_rune_id_and_name_with_lookup(r, self._perk_names)
                if not extracted:
                    continue
                rid, _name = extracted
                if rid == rune_id:
                    return slot_idx
        return None

    def _on_secondary_changed(self, index: int) -> None:
        self._secondary_last_changed = index
        self._enforce_secondary_row_constraint()

    def _set_combo_items_enabled_by_slot(self, combo: QComboBox, forbidden_slot: int | None) -> None:
        model = combo.model()
        for row in range(combo.count()):
            data = combo.itemData(row)
            slot = self._get_secondary_slot_from_data(data)
            enabled = forbidden_slot is None or slot is None or slot != forbidden_slot
            if hasattr(model, "item"):
                item = model.item(row)
                if item is not None:
                    item.setEnabled(enabled)

    def _select_first_allowed(self, combo: QComboBox, forbidden_slot: int | None) -> None:
        if forbidden_slot is None:
            return
        for row in range(combo.count()):
            data = combo.itemData(row)
            slot = self._get_secondary_slot_from_data(data)
            if slot is None or slot != forbidden_slot:
                combo.setCurrentIndex(row)
                return

    def _enforce_secondary_row_constraint(self) -> None:
        if len(self.secondary_rune_combos) < 2:
            return
        c1, c2 = self.secondary_rune_combos[0], self.secondary_rune_combos[1]

        d1, d2 = c1.currentData(), c2.currentData()
        slot1 = self._get_secondary_slot_from_data(d1)
        slot2 = self._get_secondary_slot_from_data(d2)

        c1.blockSignals(True)
        c2.blockSignals(True)
        try:
            self._set_combo_items_enabled_by_slot(c1, slot2)
            self._set_combo_items_enabled_by_slot(c2, slot1)

            if slot1 is not None and slot2 is not None and slot1 == slot2:
                if self._secondary_last_changed == 0:
                    self._select_first_allowed(c2, slot1)
                else:
                    self._select_first_allowed(c1, slot2)
        finally:
            c1.blockSignals(False)
            c2.blockSignals(False)

    def _refresh_primary_only(self) -> None:
        style_id = _safe_int(self.primary_style_combo.currentData())
        if style_id is None:
            return
        style = self._styles.get(style_id)
        if not style:
            return

        slots = _get_style_slots(style)
        for i in range(min(4, len(self.primary_rune_combos))):
            cb = self.primary_rune_combos[i]
            prev_id = _safe_int(cb.currentData())
            cb.blockSignals(True)
            cb.clear()

            slot = slots[i] if i < len(slots) else {}
            for r in _get_slot_runes(slot):
                extracted = _extract_rune_id_and_name_with_lookup(r, self._perk_names)
                if not extracted:
                    continue
                rid, name = extracted
                icon = self._get_perk_icon(rid)
                if icon is not None and not icon.isNull():
                    cb.addItem(icon, name, rid)
                else:
                    cb.addItem(name, rid)

            if prev_id is not None:
                idx = cb.findData(prev_id)
                if idx >= 0:
                    cb.setCurrentIndex(idx)
            cb.blockSignals(False)

    def _refresh_secondary_only(self) -> None:
        style_id = _safe_int(self.secondary_style_combo.currentData())
        if style_id is None:
            return
        style = self._styles.get(style_id)
        if not style:
            return

        slots = _get_style_slots(style)
        secondary_choices: list[dict[str, Any]] = []
        for slot_idx in range(1, min(4, len(slots))):
            slot = slots[slot_idx]
            for r in _get_slot_runes(slot):
                extracted = _extract_rune_id_and_name_with_lookup(r, self._perk_names)
                if not extracted:
                    continue
                rid, name = extracted
                secondary_choices.append({"id": rid, "slot": slot_idx, "name": name})

        for cb in self.secondary_rune_combos:
            prev = cb.currentData()
            prev_id = _safe_int(prev.get("id")) if isinstance(prev, dict) else _safe_int(prev)

            cb.blockSignals(True)
            cb.clear()
            for item in secondary_choices:
                icon = self._get_perk_icon(item["id"])
                if icon is not None and not icon.isNull():
                    cb.addItem(icon, item["name"], {"id": item["id"], "slot": item["slot"]})
                else:
                    cb.addItem(item["name"], {"id": item["id"], "slot": item["slot"]})

            if prev_id is not None:
                for idx in range(cb.count()):
                    data = cb.itemData(idx)
                    if isinstance(data, dict) and _safe_int(data.get("id")) == prev_id:
                        cb.setCurrentIndex(idx)
                        break
            cb.blockSignals(False)
        
        self._enforce_secondary_row_constraint()

    def _refresh_shards(self) -> None:
        def _is_stat_mod_slot(slot: Any) -> bool:
            if not isinstance(slot, dict):
                return False
            slot_type = str(slot.get("type") or "").strip().lower()
            return "statmod" in slot_type

        # Newer LCU versions expose stat shards as `kStatMod` slots inside each main style
        # (e.g. Precision/Resolve). Prefer those because they match the current client.
        primary_style_id = _safe_int(self.primary_style_combo.currentData())
        base_style = self._styles.get(primary_style_id) if primary_style_id is not None else None
        if not base_style:
            base_style = next((s for sid, s in self._styles.items() if sid in MAIN_STYLE_IDS), None)

        stat_slots: list[Any] = []
        if base_style:
            stat_slots = [s for s in _get_style_slots(base_style) if _is_stat_mod_slot(s)]

        # Older clients may expose a dedicated style (id=5000) for stat mods.
        if len(stat_slots) < 3:
            stat_style = self._styles.get(STAT_MODS_STYLE_ID)
            if not stat_style:
                for style in self._styles.values():
                    key = (style.get("key") or style.get("name") or "").strip().lower()
                    if key in ("statmods", "stat mods", "stat shards"):
                        stat_style = style
                        break
            if stat_style:
                stat_slots = _get_style_slots(stat_style)

        if len(stat_slots) < 3:
            for cb in self.shard_combos:
                cb.clear()
            self._refresh_shards_fallback()
            return

        for i in range(min(3, len(self.shard_combos))):
            cb = self.shard_combos[i]
            prev = cb.currentData()
            prev_id = _safe_int(prev)

            cb.blockSignals(True)
            cb.clear()
            slot = stat_slots[i] if i < len(stat_slots) else {}
            for r in _get_slot_runes(slot):
                extracted = _extract_rune_id_and_name_with_lookup(r, self._perk_names)
                if not extracted:
                    continue
                rid, name = extracted
                icon = self._get_perk_icon(rid)
                if icon is not None and not icon.isNull():
                    cb.addItem(icon, name, rid)
                else:
                    cb.addItem(name, rid)

            if prev_id is not None:
                idx = cb.findData(prev_id)
                if idx >= 0:
                    cb.setCurrentIndex(idx)
            if cb.count() > 0 and cb.currentIndex() < 0:
                cb.setCurrentIndex(0)

            options = [cb.itemText(j) for j in range(cb.count())]
            cb.setToolTip("Seçenekler: " + " / ".join(options) if options else "")
            cb.blockSignals(False)

        if any(cb.count() == 0 for cb in self.shard_combos):
            self._refresh_shards_fallback()

    def _refresh_shards_fallback(self) -> None:
        fallback_rows = [
            [5005, 5008, 5007],
            [5008, 5002, 5003],
            [5001, 5002, 5003],
        ]

        for i, cb in enumerate(self.shard_combos):
            prev_id = _safe_int(cb.currentData())
            cb.blockSignals(True)
            cb.clear()

            row_ids = fallback_rows[i] if i < len(fallback_rows) else []
            for rid in row_ids:
                rid_int = int(rid)
                name = self._perk_names.get(rid_int) or str(rid_int)
                icon = self._get_perk_icon(rid_int)
                if icon is not None and not icon.isNull():
                    cb.addItem(icon, name, rid_int)
                else:
                    cb.addItem(name, rid_int)

            if prev_id is not None:
                idx = cb.findData(prev_id)
                if idx >= 0:
                    cb.setCurrentIndex(idx)
            if cb.count() > 0 and cb.currentIndex() < 0:
                cb.setCurrentIndex(0)

            options = [cb.itemText(j) for j in range(cb.count())]
            cb.setToolTip("Seçenekler: " + " / ".join(options) if options else "")
            cb.blockSignals(False)

    def _refresh_summary(self) -> None:
        page = self.get_rune_page(allow_incomplete=True)
        if not page:
            self.summary_label.setText("")
            return
        self.summary_label.setText(
            f"primaryStyleId={page.get('primaryStyleId')}  "
            f"subStyleId={page.get('subStyleId')}  "
            f"selectedPerkIds={page.get('selectedPerkIds')}"
        )

    def _apply_existing_page(self, page: dict[str, Any], *, fallback_name: str) -> None:
        name = str(page.get("name") or fallback_name)
        self.name_edit.setText(name)

        primary_style_id = _safe_int(page.get("primaryStyleId"))
        secondary_style_id = _safe_int(page.get("subStyleId"))
        if primary_style_id is not None:
            idx = self.primary_style_combo.findData(primary_style_id)
            if idx >= 0:
                self.primary_style_combo.setCurrentIndex(idx)
        self._rebuild_secondary_style_items()
        if secondary_style_id is not None:
            idx = self.secondary_style_combo.findData(secondary_style_id)
            if idx >= 0:
                self.secondary_style_combo.setCurrentIndex(idx)

        self._refresh_all()

        perk_ids = page.get("selectedPerkIds")
        if not isinstance(perk_ids, list):
            return

        perk_ints = [pid for pid in (_safe_int(x) for x in perk_ids) if pid is not None]
        if len(perk_ints) < 6:
            return

        primary_ids = perk_ints[:4]
        secondary_ids = perk_ints[4:6]
        shard_ids = perk_ints[6:9]

        for combo, rid in zip(self.primary_rune_combos, primary_ids):
            idx = combo.findData(rid)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        for combo, rid in zip(self.secondary_rune_combos, secondary_ids):
            for idx in range(combo.count()):
                data = combo.itemData(idx)
                if isinstance(data, dict) and _safe_int(data.get("id")) == rid:
                    combo.setCurrentIndex(idx)
                    break

        for combo, rid in zip(self.shard_combos, shard_ids):
            idx = combo.findData(rid)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def _on_delete(self) -> None:
        if QMessageBox.question(
            self,
            "Remove Custom",
            "Remove the saved custom rune page for this champion?",
        ) != QMessageBox.StandardButton.Yes:
            return
        self.action = "delete"
        self.accept()

    def _on_save(self) -> None:
        page = self.get_rune_page(allow_incomplete=False)
        if not page:
            return
        self.action = "save"
        self.accept()

    def get_rune_page(self, *, allow_incomplete: bool = False) -> dict[str, Any] | None:
        """UI seçimlerinden LCU rune page payload'ı üretir."""
        primary_style_id = _safe_int(self.primary_style_combo.currentData())
        secondary_style_id = _safe_int(self.secondary_style_combo.currentData())
        if primary_style_id is None or secondary_style_id is None:
            if allow_incomplete:
                return None
            QMessageBox.warning(self, "Missing", "Select both primary and secondary paths.")
            return None

        primary_ids: list[int] = []
        for cb in self.primary_rune_combos:
            rid = _safe_int(cb.currentData())
            if rid is None:
                if allow_incomplete:
                    return None
                QMessageBox.warning(self, "Missing", "Select all primary runes.")
                return None
            primary_ids.append(rid)

        secondary_ids: list[int] = []
        secondary_slots: list[int] = []
        for cb in self.secondary_rune_combos:
            data = cb.currentData()
            if isinstance(data, dict):
                rid = _safe_int(data.get("id"))
                slot = _safe_int(data.get("slot"))
            else:
                rid = _safe_int(data)
                slot = None
            if rid is None:
                if allow_incomplete:
                    return None
                QMessageBox.warning(self, "Missing", "Select both secondary runes.")
                return None
            secondary_ids.append(rid)
            if slot is None and secondary_style_id is not None:
                slot = self._infer_secondary_slot(secondary_style_id, rid)
            if slot is not None:
                secondary_slots.append(slot)

        if len(secondary_ids) == 2 and secondary_ids[0] == secondary_ids[1]:
            if allow_incomplete:
                return None
            QMessageBox.warning(self, "Invalid", "Secondary runes cannot be the same.")
            return None

        if len(secondary_slots) == 2 and secondary_slots[0] == secondary_slots[1]:
            if allow_incomplete:
                return None
            QMessageBox.warning(self, "Invalid", "Secondary runes must be from different rows.")
            return None

        shard_ids: list[int] = []
        for cb in self.shard_combos:
            rid = _safe_int(cb.currentData())
            if rid is None:
                if allow_incomplete:
                    return None
                QMessageBox.warning(self, "Missing", "Select all shards.")
                return None
            shard_ids.append(rid)

        name = self.name_edit.text().strip() or "Custom"
        return {
            "name": name,
            "primaryStyleId": primary_style_id,
            "subStyleId": secondary_style_id,
            "selectedPerkIds": primary_ids + secondary_ids + shard_ids,
        }
