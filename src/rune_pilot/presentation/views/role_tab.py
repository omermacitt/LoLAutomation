"""
One tab of the main window: the ban and champion picks for a single role.

Each tab owns three champion rows, and a row is a champion plus everything attached
to it — its two summoner spells, which rune page to use, and which skin. Keeping a row
together in one object is what removes the parallel `role_rune_buttons[role][i]` /
`role_skin_buttons[role][i]` lookups the main window used to do.

Shared, cross-role state (rune presets, skins, spells) lives in
`ChampionSelectionModel`; a tab only renders it and writes user edits back.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QWidget,
)

from rune_pilot.domain.constants import SPELL_NAME_BY_ID, SUMMONER_SPELLS
from rune_pilot.domain.game_data import SkinOptions
from rune_pilot.presentation.api_client import ApiClient
from rune_pilot.presentation.controllers.background_query import BackgroundQuery
from rune_pilot.presentation.dialogs.rune_presets_dialog import RunePresetsDialog
from rune_pilot.presentation.dialogs.skins_dialog import SkinSelectDialog
from rune_pilot.presentation.view_models.selection_model import (
    RECOMMENDED_SLOT,
    ChampionSelectionModel,
)
from rune_pilot.presentation.widgets.combo_utils import exclude_between, set_combo_by_data
from rune_pilot.presentation.widgets.searchable_combo import make_combo_searchable

CHAMPIONS_PER_ROLE = 3
NONE_LABEL = "None"
RUNE_SLOTS = (1, 2, 3)

_SPELL_COMBO_WIDTH = 155
_RUNE_SELECT_WIDTH = 140
_BUTTON_WIDTH = 95

_ROW_LABELS = (
    "1st Champion (Highest priority):",
    "2nd Champion:",
    "3rd Champion:",
)


@dataclass(frozen=True)
class ChampionRow:
    """The widgets making up one champion line."""

    champion: QComboBox
    spell1: QComboBox
    spell2: QComboBox
    rune_select: QComboBox
    rune_button: QPushButton
    skin_button: QPushButton

    @property
    def champion_id(self) -> int | None:
        value = self.champion.currentData()
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


class RoleTab(QWidget):
    """Ban pick plus three champion rows for one role."""

    # A champion pick changed. The main window listens because rune and skin state is
    # shared across roles, so every other tab has to re-render too.
    champion_changed = pyqtSignal()

    def __init__(
        self,
        role_key: str,
        model: ChampionSelectionModel,
        roles_with_champion: Callable[[int], set[str]],
        parent: QWidget | None = None,
        *,
        api_client: ApiClient | None = None,
    ) -> None:
        super().__init__(parent)
        self.role_key = role_key
        self.model = model
        self._roles_with_champion = roles_with_champion
        self._client = api_client if api_client is not None else ApiClient()
        self._skin_query = BackgroundQuery(self)
        self._skin_query.succeeded.connect(self._show_skin_dialog)
        self._skin_query.failed.connect(self._skin_query_failed)
        self._skin_query.finished.connect(self._skin_query_finished)
        self._skin_request: tuple[int, int, str] | None = None
        # Guards the combos while we write into them, so programmatic updates do not
        # come back through the user-edit handlers.
        self._suspend_spell_signals = False

        layout = QFormLayout(self)

        self.ban_combo = QComboBox()
        make_combo_searchable(self.ban_combo, placeholder="Search ban...")
        layout.addRow("Ban Champion:", self.ban_combo)

        self.rows: list[ChampionRow] = []
        for index in range(CHAMPIONS_PER_ROLE):
            row = self._build_row(index)
            self.rows.append(row)
            layout.addRow(_ROW_LABELS[index], self._row_widget(row, index))

    # -- construction --------------------------------------------------------

    def _build_row(self, index: int) -> ChampionRow:
        champion = QComboBox()
        make_combo_searchable(champion)

        spell1 = QComboBox()
        spell2 = QComboBox()
        for name in SUMMONER_SPELLS:
            spell1.addItem(name)
            spell2.addItem(name)
        spell1.setToolTip("Spell 1")
        spell2.setToolTip("Spell 2")

        default_spell1, default_spell2 = self._default_spell_names()
        spell1.setCurrentText(default_spell1)
        spell2.setCurrentText(default_spell2)
        for combo in (spell1, spell2):
            combo.setFixedWidth(_SPELL_COMBO_WIDTH)
            # Stays disabled until a champion is picked — spells are per champion.
            combo.setEnabled(False)

        rune_select = QComboBox()
        rune_select.setFixedWidth(_RUNE_SELECT_WIDTH)
        rune_select.setToolTip("Rune page to use for this champion")

        rune_button = QPushButton("Runes")
        rune_button.setObjectName("runeButton")
        rune_button.setFixedWidth(_BUTTON_WIDTH)

        skin_button = QPushButton("Skin")
        skin_button.setObjectName("skinButton")
        skin_button.setFixedWidth(_BUTTON_WIDTH)

        row = ChampionRow(champion, spell1, spell2, rune_select, rune_button, skin_button)

        champion.currentIndexChanged.connect(lambda _=0, i=index: self._on_champion_changed(i))
        spell1.currentIndexChanged.connect(lambda _=0, i=index: self._on_spell_changed(i, "spell1"))
        spell2.currentIndexChanged.connect(lambda _=0, i=index: self._on_spell_changed(i, "spell2"))
        rune_select.currentIndexChanged.connect(
            lambda _=0, i=index: self._on_rune_selection_changed(i)
        )
        rune_button.clicked.connect(lambda _=False, i=index: self.open_rune_dialog(i))
        skin_button.clicked.connect(lambda _=False, i=index: self.open_skin_dialog(i))

        exclude_between(spell1, spell2, none_label=NONE_LABEL)
        return row

    def _row_widget(self, row: ChampionRow, index: int) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(row.champion, 1)
        layout.addWidget(row.spell1)
        layout.addWidget(row.spell2)
        layout.addWidget(row.rune_select)
        layout.addWidget(row.rune_button)
        layout.addWidget(row.skin_button)
        self._refresh_row(index)
        return container

    def _default_spell_names(self) -> tuple[str, str]:
        return ("Flash", "Smite") if self.role_key == "JUNGLE" else ("Flash", "Ignite")

    # -- population ----------------------------------------------------------

    def set_ban_options(self, champions: list[tuple[int, str]]) -> None:
        self.ban_combo.clear()
        self.ban_combo.addItem(NONE_LABEL, None)
        for champ_id, name in champions:
            self.ban_combo.addItem(name, champ_id)

    def set_champion_options(self, champions: list[tuple[int, str]]) -> None:
        for row in self.rows:
            row.champion.blockSignals(True)
            try:
                row.champion.clear()
                row.champion.addItem("Select", None)
                for champ_id, name in champions:
                    row.champion.addItem(name, champ_id)
            finally:
                row.champion.blockSignals(False)

    def restore(self, ban_id: int | None, champion_ids: list[int | None]) -> None:
        """Re-selects saved picks without firing change handlers."""
        set_combo_by_data(self.ban_combo, ban_id)
        for index, champ_id in enumerate(champion_ids[:CHAMPIONS_PER_ROLE]):
            combo = self.rows[index].champion
            combo.blockSignals(True)
            try:
                set_combo_by_data(combo, champ_id)
            finally:
                combo.blockSignals(False)

    # -- reading the user's picks -------------------------------------------

    @property
    def ban_id(self) -> int | None:
        value = self.ban_combo.currentData()
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def champion_ids(self, *, include_empty: bool = False) -> list[int | None]:
        ids = [row.champion_id for row in self.rows]
        return ids if include_empty else [cid for cid in ids if cid is not None]

    def has_champion(self, champ_id: int) -> bool:
        return any(row.champion_id == champ_id for row in self.rows)

    def first_spell_pair(self) -> dict[str, int | None] | None:
        """
        The spells of the highest-priority picked champion.

        The API takes one pair per role, so the first filled row wins — matching the
        pick order the automation itself follows.
        """
        for row in self.rows:
            if row.champion_id is None:
                continue
            return {
                "spell1Id": SUMMONER_SPELLS.get(row.spell1.currentText()),
                "spell2Id": SUMMONER_SPELLS.get(row.spell2.currentText()),
            }
        return None

    def sync_spells_into_model(self) -> None:
        """Writes every visible spell pair back to the model before a save or a start."""
        for row in self.rows:
            champ_id = row.champion_id
            if champ_id is None:
                continue
            self.model.set_spells(
                self.role_key,
                champ_id,
                SUMMONER_SPELLS.get(row.spell1.currentText()),
                SUMMONER_SPELLS.get(row.spell2.currentText()),
                notify=False,
            )

    # -- rendering -----------------------------------------------------------

    def refresh(self) -> None:
        """Re-renders every row from the model."""
        for index in range(len(self.rows)):
            self._refresh_row(index)

    def _refresh_row(self, index: int) -> None:
        self._refresh_spells(index)
        self._refresh_rune_select(index)
        self._refresh_rune_button(index)
        self._refresh_skin_button(index)

    def _refresh_spells(self, index: int) -> None:
        row = self.rows[index]
        champ_id = row.champion_id
        if champ_id is None:
            row.spell1.setEnabled(False)
            row.spell2.setEnabled(False)
            return

        entry = self.model.spells_for(self.role_key, champ_id)
        if entry is None:
            default_spell1, default_spell2 = self._default_spell_names()
            spell1_id = SUMMONER_SPELLS.get(default_spell1)
            spell2_id = SUMMONER_SPELLS.get(default_spell2)
        else:
            spell1_id = entry.get("spell1Id")
            spell2_id = entry.get("spell2Id")

        self._suspend_spell_signals = True
        try:
            row.spell1.setEnabled(True)
            row.spell2.setEnabled(True)
            row.spell1.setCurrentText(_spell_name(spell1_id))
            row.spell2.setCurrentText(_spell_name(spell2_id))

            if spell1_id is not None and spell1_id == spell2_id:
                # Can happen with a hand-edited config; the same spell twice is not
                # a state the client accepts.
                row.spell2.setCurrentText(NONE_LABEL)
                spell2_id = None

            exclude_between(row.spell1, row.spell2, none_label=NONE_LABEL)
        finally:
            self._suspend_spell_signals = False

        self.model.set_spells(self.role_key, champ_id, spell1_id, spell2_id, notify=False)

    def _refresh_rune_select(self, index: int) -> None:
        row = self.rows[index]
        champ_id = row.champion_id

        row.rune_select.blockSignals(True)
        try:
            row.rune_select.clear()
            row.rune_select.addItem("Use default (inherited)", -1)
            row.rune_select.addItem("Recommended", RECOMMENDED_SLOT)

            if champ_id is None:
                row.rune_select.setEnabled(False)
                row.rune_select.setCurrentIndex(0)
                return

            presets = self.model.presets(champ_id)
            for slot in RUNE_SLOTS:
                page = presets.get(str(slot))
                if not isinstance(page, dict):
                    continue
                name = " ".join(str(page.get("name") or "").split())
                row.rune_select.addItem(
                    f"Custom {slot}: {name}" if name else f"Custom {slot}", slot
                )

            choice = self.model.selected_slot(champ_id, self.role_key)
            inherited = not self.model.has_role_assignment(champ_id, self.role_key)
            default = self.model.selected_slot(champ_id)
            row.rune_select.setItemText(
                0, f"Default: {'Preset ' + str(default) if default else 'Recommended'}"
            )
            selected = row.rune_select.findData(-1 if inherited else choice)
            row.rune_select.setCurrentIndex(selected if selected >= 0 else 0)
            # Nothing to choose between when only "Recommended" is there.
            row.rune_select.setEnabled(row.rune_select.count() > 1)
        finally:
            row.rune_select.blockSignals(False)

    def _refresh_rune_button(self, index: int) -> None:
        row = self.rows[index]
        champ_id = row.champion_id

        if champ_id is None:
            row.rune_button.setEnabled(False)
            row.rune_button.setText("Runes")
            row.rune_button.setToolTip("")
            _set_configured(row.rune_button, False)
            return

        count = self.model.preset_count(champ_id)
        row.rune_button.setEnabled(True)
        row.rune_button.setText(f"Runes ({count})" if count else "Runes")
        row.rune_button.setToolTip(
            f"{count} custom rune preset(s) saved" if count else "Recommended rune will be used"
        )
        _set_configured(row.rune_button, count > 0)

    def _refresh_skin_button(self, index: int) -> None:
        row = self.rows[index]
        champ_id = row.champion_id

        if champ_id is None:
            row.skin_button.setEnabled(False)
            row.skin_button.setText("Skin")
            row.skin_button.setToolTip("Select a champion first")
            _set_configured(row.skin_button, False)
            return

        has_custom = self.model.has_skin(self.role_key, champ_id)
        row.skin_button.setEnabled(True)
        row.skin_button.setText("Skin (Custom)" if has_custom else "Skin")
        row.skin_button.setToolTip(
            "Custom skin selected" if has_custom else "Default skin will be used"
        )
        _set_configured(row.skin_button, has_custom)

    # -- user edits ----------------------------------------------------------

    def _on_champion_changed(self, index: int) -> None:
        champ_id = self.rows[index].champion_id
        if champ_id is not None:
            self.model.inherit_skin_across_roles(self.role_key, champ_id)
        # Rune and skin state is shared across roles, so the whole window re-renders.
        self.champion_changed.emit()

    def _on_spell_changed(self, index: int, changed: str) -> None:
        if self._suspend_spell_signals:
            return

        row = self.rows[index]
        champ_id = row.champion_id
        if champ_id is None:
            return

        self._suspend_spell_signals = True
        try:
            if (
                row.spell1.currentText() != NONE_LABEL
                and row.spell1.currentText() == row.spell2.currentText()
            ):
                # Both slots now hold the same spell; clear the one the user did not touch.
                other = row.spell2 if changed == "spell1" else row.spell1
                other.setCurrentText(NONE_LABEL)
            exclude_between(row.spell1, row.spell2, none_label=NONE_LABEL)
        finally:
            self._suspend_spell_signals = False

        self.model.set_spells(
            self.role_key,
            champ_id,
            SUMMONER_SPELLS.get(row.spell1.currentText()),
            SUMMONER_SPELLS.get(row.spell2.currentText()),
        )

    def _on_rune_selection_changed(self, index: int) -> None:
        row = self.rows[index]
        champ_id = row.champion_id
        if champ_id is None:
            return
        try:
            slot = int(row.rune_select.currentData() or RECOMMENDED_SLOT)
        except (TypeError, ValueError):
            slot = RECOMMENDED_SLOT
        self.model.set_selected_slot(champ_id, slot, self.role_key)

    # -- dialogs -------------------------------------------------------------

    def open_rune_dialog(self, index: int) -> None:
        row = self.rows[index]
        champ_id = row.champion_id
        if champ_id is None:
            QMessageBox.warning(self, "No Selection", "Please select a champion first.")
            return

        presets = self.model.presets(champ_id)
        dialog = RunePresetsDialog(
            champion_id=champ_id,
            champion_name=row.champion.currentText(),
            role_name=self.role_key,
            impact_roles=lambda slot, cid=champ_id: self.model.roles_using_preset(cid, slot),
            existing_presets=presets,
            initial_slot=self._initial_rune_slot(champ_id, presets),
            on_save_preset=lambda slot, page, cid=champ_id: self.model.save_preset(
                cid, slot, page, self.role_key
            ),
            on_delete_preset=lambda slot, cid=champ_id: self.model.delete_preset(cid, slot),
            api_client=self._client,
            parent=self,
        )
        dialog.exec()

    def _initial_rune_slot(self, champ_id: int, presets: dict[str, dict]) -> int:
        """Opens on the selected preset, else the first one that exists, else slot 1."""
        selected = self.model.selected_slot(champ_id, self.role_key)
        if selected in RUNE_SLOTS:
            return selected
        for slot in RUNE_SLOTS:
            if isinstance(presets.get(str(slot)), dict):
                return slot
        return 1

    def open_skin_dialog(self, index: int) -> None:
        row = self.rows[index]
        champ_id = row.champion_id
        if champ_id is None:
            QMessageBox.warning(self, "No Selection", "Please select a champion first.")
            return

        if self._skin_query.busy:
            return
        self._skin_request = (index, champ_id, row.champion.currentText())
        self._skin_query.run(lambda: self._client.skin_options(champ_id))
        row.skin_button.setEnabled(False)
        row.skin_button.setText("Loading…")

    def _show_skin_dialog(self, result: SkinOptions) -> None:
        if self._skin_request is None:
            return
        index, champ_id, name = self._skin_request
        if self.rows[index].champion_id != champ_id or result.champion_id != champ_id:
            return
        base_skin_id = champ_id * 1000
        current = self.model.skin_for(self.role_key, champ_id)
        if current is None:
            current = self.model.find_skin_in_any_role(champ_id)

        dialog = SkinSelectDialog(
            champion_name=name,
            skins=[(skin.id, skin.name) for skin in result.skins],
            selected_skin_id=int(current) if current is not None else base_skin_id,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if self.rows[index].champion_id != champ_id:
            return

        try:
            new_skin_id = int(dialog.get_selected_skin_id())
        except (TypeError, ValueError):
            return

        if new_skin_id == base_skin_id:
            self.model.clear_skin(champ_id)
            return

        # Apply to this role plus any other role that picked the same champion, so one
        # champion does not show up with two different skins.
        self.model.set_skin(
            champ_id,
            new_skin_id,
            {self.role_key} | self._roles_with_champion(champ_id),
        )

    def _skin_query_failed(self, error: str) -> None:
        if (
            self._skin_request is not None
            and self.rows[self._skin_request[0]].champion_id == self._skin_request[1]
        ):
            QMessageBox.critical(self, "Error", f"Could not retrieve skin list:\n{error}")

    def _skin_query_finished(self) -> None:
        if self._skin_request is not None:
            self._refresh_skin_button(self._skin_request[0])
        self._skin_request = None

    def shutdown(self) -> None:
        self._skin_query.shutdown()


def _spell_name(spell_id: int | None) -> str:
    if spell_id is None:
        return NONE_LABEL
    return SPELL_NAME_BY_ID.get(int(spell_id), NONE_LABEL)


def _set_configured(button: QPushButton, configured: bool) -> None:
    """Flags a button as holding a custom value, for the `configured` QSS selector."""
    if button.property("configured") == bool(configured):
        return
    button.setProperty("configured", bool(configured))
    button.style().unpolish(button)
    button.style().polish(button)
    button.update()
