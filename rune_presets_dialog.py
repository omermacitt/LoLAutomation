"""
RunePilot çoklu özel rün preset yönetimi (PyQt6).

Tek bir pencerede Özel 1/2/3 presetleri arasında sayfalama ile gezip
kaydetme/silme imkanı verir.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
)

from runes_dialog import RunePageDialog


class RunePresetsDialog(QDialog):
    def __init__(
        self,
        *,
        champion_id: int,
        champion_name: str,
        existing_presets: dict[str, dict] | None,
        initial_slot: int = 1,
        on_save_preset: Callable[[int, dict], None],
        on_delete_preset: Callable[[int], None],
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._champion_id = int(champion_id)
        self._champion_name = str(champion_name)
        self._on_save_preset = on_save_preset
        self._on_delete_preset = on_delete_preset

        presets = existing_presets if isinstance(existing_presets, dict) else {}
        self._saved_slots: set[int] = set()
        for k, v in presets.items():
            if str(k) in ("1", "2", "3") and isinstance(v, dict):
                self._saved_slots.add(int(k))

        self.setWindowTitle(f"Özel Rünler - {self._champion_name}")
        self.setMinimumWidth(700)

        root = QVBoxLayout(self)

        title = QLabel(f"Şampiyon: {self._champion_name}")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        root.addWidget(title)

        nav = QHBoxLayout()
        self.prev_btn = QPushButton("◀")
        self.next_btn = QPushButton("▶")
        self.prev_btn.setFixedWidth(40)
        self.next_btn.setFixedWidth(40)
        self.prev_btn.clicked.connect(lambda _=False: self._go(-1))
        self.next_btn.clicked.connect(lambda _=False: self._go(1))

        self.slot_label = QLabel("")
        self.slot_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        nav.addWidget(self.prev_btn)
        nav.addWidget(self.slot_label, 1)
        nav.addWidget(self.next_btn)
        root.addLayout(nav)

        self.stack = QStackedWidget()
        self._editors: dict[int, RunePageDialog] = {}
        for slot in (1, 2, 3):
            page = presets.get(str(slot)) if isinstance(presets, dict) else None
            editor = RunePageDialog(
                champion_name=self._champion_name,
                existing_page=page if isinstance(page, dict) else None,
                parent=self,
                show_buttons=False,
            )
            self._editors[slot] = editor
            self.stack.addWidget(editor)
        root.addWidget(self.stack, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)

        self.delete_btn = QPushButton("Sil")
        self.delete_btn.clicked.connect(self._delete_current)
        actions.addWidget(self.delete_btn)

        self.save_btn = QPushButton("Kaydet")
        self.save_btn.clicked.connect(self._save_current)
        actions.addWidget(self.save_btn)

        close_btn = QPushButton("Kapat")
        close_btn.clicked.connect(self.close)
        actions.addWidget(close_btn)

        root.addLayout(actions)

        if initial_slot not in (1, 2, 3):
            initial_slot = 1
        self._set_slot(initial_slot)

    def _current_slot(self) -> int:
        return int(self.stack.currentIndex()) + 1

    def _set_slot(self, slot: int) -> None:
        slot = 1 if slot not in (1, 2, 3) else int(slot)
        self.stack.setCurrentIndex(slot - 1)
        self._refresh_header()

    def _go(self, delta: int) -> None:
        slot = self._current_slot()
        slot = max(1, min(3, slot + int(delta)))
        self._set_slot(slot)

    def _refresh_header(self) -> None:
        slot = self._current_slot()
        saved = slot in self._saved_slots
        self.slot_label.setText(f"Özel {slot} / 3" + (" (Kayıtlı)" if saved else " (Boş)"))
        self.prev_btn.setEnabled(slot > 1)
        self.next_btn.setEnabled(slot < 3)
        self.delete_btn.setEnabled(saved)

    def _save_current(self) -> None:
        slot = self._current_slot()
        editor = self._editors.get(slot)
        if editor is None:
            return
        page = editor.get_rune_page(allow_incomplete=False)
        if not page:
            return
        self._on_save_preset(slot, page)
        self._saved_slots.add(slot)
        self._refresh_header()

    def _delete_current(self) -> None:
        slot = self._current_slot()
        if slot not in self._saved_slots:
            return
        self._on_delete_preset(slot)
        self._saved_slots.discard(slot)
        self._refresh_header()

