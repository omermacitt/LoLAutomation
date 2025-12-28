"""
RunePilot kostüm (skin) seçim penceresi (PyQt6).

Kullanıcıya seçili şampiyon için sahip olduğu kostümleri listeler ve seçilen
`skinId` değerini döndürür.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class SkinSelectDialog(QDialog):
    def __init__(
        self,
        *,
        champion_name: str,
        skins: list[tuple[int, str]],
        selected_skin_id: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._selected_skin_id: int | None = selected_skin_id

        self.setWindowTitle("Kostüm Seç")
        self.setModal(True)
        self.resize(420, 140)

        layout = QVBoxLayout(self)

        title = QLabel(f"Şampiyon: {champion_name}")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        self.combo = QComboBox()
        for skin_id, display_name in skins:
            self.combo.addItem(display_name, int(skin_id))

        if selected_skin_id is not None:
            idx = self.combo.findData(int(selected_skin_id))
            if idx >= 0:
                self.combo.setCurrentIndex(idx)

        layout.addWidget(self.combo)

        buttons = QHBoxLayout()
        buttons.addStretch(1)

        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        ok_btn = QPushButton("Kaydet")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True)
        buttons.addWidget(ok_btn)

        layout.addLayout(buttons)

    def get_selected_skin_id(self) -> int | None:
        try:
            val = self.combo.currentData()
        except Exception:
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

