"""Small QComboBox helpers shared by the main window and the role tabs."""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QComboBox


def set_combo_item_enabled(combo: QComboBox, index: int, enabled: bool) -> None:
    """
    Greys out one entry without removing it.

    Used for mutual exclusion — a role already chosen as first preference, or a spell
    already in the other slot — where the item should stay visible but unpickable. Only
    works on a combo backed by a QStandardItemModel; it is a no-op otherwise.
    """
    try:
        item = combo.model().item(index)  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        return
    if item is None:
        return
    try:
        item.setEnabled(bool(enabled))
    except (AttributeError, RuntimeError):
        return


def set_all_combo_items_enabled(combo: QComboBox, enabled: bool = True) -> None:
    for index in range(combo.count()):
        set_combo_item_enabled(combo, index, enabled)


def exclude_between(first: QComboBox, second: QComboBox, *, none_label: str = "None") -> None:
    """
    Stops the same value being chosen in both combos.

    Re-enables everything first, then disables each combo's current choice in the
    other one. `none_label` is exempt, since both may legitimately be "None".
    """
    set_all_combo_items_enabled(first)
    set_all_combo_items_enabled(second)

    for source, target in ((first, second), (second, first)):
        text = source.currentText()
        if text == none_label:
            continue
        index = target.findText(text)
        if index >= 0:
            set_combo_item_enabled(target, index, False)


def set_combo_by_data(combo: QComboBox, value: Any) -> None:
    """Selects the entry carrying `value` as its user data, or the first entry for None."""
    if value is None:
        combo.setCurrentIndex(0)  # the "Select" / "None" placeholder
        return
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)
