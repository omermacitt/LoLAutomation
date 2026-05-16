"""
Aranabilir QComboBox widget'ı.

QComboBox'a type-ahead (yaz-ara) davranışı ekleyen yardımcı sınıf ve fonksiyon.
"""

from PyQt6.QtCore import Qt, QTimer, QObject, QEvent
from PyQt6.QtWidgets import QComboBox, QCompleter


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
