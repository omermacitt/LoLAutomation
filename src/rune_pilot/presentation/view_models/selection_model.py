"""
The user's per-champion choices: rune presets, skins and summoner spells.

These four maps used to live as loose dicts on `MainWindow`, edited in place from a
dozen methods. They belong together because they are keyed differently and read across
roles: rune data is keyed by champion alone (a champion's presets are the same in every
role), while skins and spells are keyed by role *and* champion. Getting that wrong is
what produced the "copy the skin over from whichever role has one" special cases.

Every mutation emits `changed`, which the main window uses as its single cue to save
the config and re-render the tabs.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from rune_pilot.domain.user_config import RUNE_SLOTS, UserConfig

RECOMMENDED_SLOT = 0


class ChampionSelectionModel(QObject):
    """Rune presets, skin choices and spell pairs, shared by every role tab."""

    changed = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # champId(str) -> slot("1"|"2"|"3") -> rune page
        self._custom_runes: dict[str, dict[str, dict]] = {}
        # champId(str) -> slot(1|2|3); absent means "recommended"
        self._rune_selection: dict[str, int] = {}
        # role -> champId(str) -> skinId
        self._custom_skins: dict[str, dict[str, int]] = {}
        # role -> champId(str) -> {"spell1Id", "spell2Id"}
        self._custom_spells: dict[str, dict[str, dict[str, int | None]]] = {}

    # -- config round-trip ---------------------------------------------------

    def load(self, config: UserConfig) -> None:
        """
        Replaces all state from a loaded config.

        Emits `changed` once at the end rather than per field, so a load costs one
        re-render instead of four.
        """
        self._custom_runes = dict(config.custom_runes)
        self._rune_selection = dict(config.rune_selection)
        self._custom_skins = dict(config.custom_skins)
        self._custom_spells = dict(config.custom_summoner_spells)
        self.changed.emit()

    def write_into(self, config: UserConfig) -> None:
        """Copies this model's state onto `config` ahead of a save."""
        config.custom_runes = self._custom_runes
        config.rune_selection = self._rune_selection
        config.custom_skins = self._custom_skins
        config.custom_summoner_spells = self._custom_spells

    # -- runes ---------------------------------------------------------------

    def presets(self, champ_id: Any) -> dict[str, dict]:
        """The champion's saved rune pages, keyed by slot."""
        presets = self._custom_runes.get(str(champ_id))
        return presets if isinstance(presets, dict) else {}

    def preset_count(self, champ_id: Any) -> int:
        return sum(1 for slot in self.presets(champ_id) if slot in RUNE_SLOTS)

    def selected_slot(self, champ_id: Any) -> int:
        """
        The slot to use for this champion, or 0 for the recommended page.

        Falls back to 0 when the stored slot no longer has a preset behind it, which
        happens after a preset is deleted from another role's tab.
        """
        try:
            slot = int(
                self._rune_selection.get(str(champ_id), RECOMMENDED_SLOT) or RECOMMENDED_SLOT
            )
        except (TypeError, ValueError):
            return RECOMMENDED_SLOT
        if str(slot) not in RUNE_SLOTS or str(slot) not in self.presets(champ_id):
            return RECOMMENDED_SLOT
        return slot

    def set_selected_slot(self, champ_id: Any, slot: int) -> None:
        champ_key = str(champ_id)
        if str(slot) in RUNE_SLOTS:
            self._rune_selection[champ_key] = int(slot)
        else:
            # Absence means "recommended", which keeps the saved config small.
            self._rune_selection.pop(champ_key, None)
        self.changed.emit()

    def save_preset(self, champ_id: Any, slot: int, page: dict) -> None:
        """Stores a rune page and selects it, mirroring what the dialog just did."""
        if str(slot) not in RUNE_SLOTS:
            return
        champ_key = str(champ_id)
        self._custom_runes.setdefault(champ_key, {})[str(slot)] = _clone_page(page)
        self._rune_selection[champ_key] = int(slot)
        self.changed.emit()

    def delete_preset(self, champ_id: Any, slot: int) -> None:
        if str(slot) not in RUNE_SLOTS:
            return
        champ_key = str(champ_id)
        presets = self._custom_runes.get(champ_key)
        if isinstance(presets, dict):
            presets.pop(str(slot), None)
            if not presets:
                self._custom_runes.pop(champ_key, None)

        if self._rune_selection.get(champ_key) == int(slot):
            self._rune_selection.pop(champ_key, None)
        self.changed.emit()

    # -- skins ---------------------------------------------------------------

    def skin_for(self, role_key: str, champ_id: Any) -> int | None:
        role_skins = self._custom_skins.get(role_key)
        if not isinstance(role_skins, dict):
            return None
        return role_skins.get(str(champ_id))

    def has_skin(self, role_key: str, champ_id: Any) -> bool:
        return self.skin_for(role_key, champ_id) is not None

    def find_skin_in_any_role(self, champ_id: Any) -> int | None:
        """A skin this champion has in some other role, used as the default."""
        champ_key = str(champ_id)
        for skins in self._custom_skins.values():
            if not isinstance(skins, dict):
                continue
            value = skins.get(champ_key)
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
        return None

    def set_skin(self, champ_id: Any, skin_id: int, role_keys: set[str]) -> None:
        """Applies one skin to this champion across every given role."""
        champ_key = str(champ_id)
        for role_key in role_keys:
            self._custom_skins.setdefault(role_key, {})[champ_key] = int(skin_id)
        self.changed.emit()

    def clear_skin(self, champ_id: Any) -> None:
        """Drops the custom skin everywhere, so the champion falls back to default."""
        champ_key = str(champ_id)
        for role_key in list(self._custom_skins):
            skins = self._custom_skins.get(role_key)
            if not isinstance(skins, dict):
                continue
            skins.pop(champ_key, None)
            if not skins:
                self._custom_skins.pop(role_key, None)
        self.changed.emit()

    def inherit_skin_across_roles(self, role_key: str, champ_id: Any) -> None:
        """
        Gives a newly picked champion the skin it already uses in another role.

        Silent — no `changed` — because this runs while a combo box is being populated
        and would otherwise trigger a save on every champion swap.
        """
        if self.has_skin(role_key, champ_id):
            return
        skin_id = self.find_skin_in_any_role(champ_id)
        if skin_id is not None:
            self._custom_skins.setdefault(role_key, {})[str(champ_id)] = skin_id

    # -- summoner spells -----------------------------------------------------

    def spells_for(self, role_key: str, champ_id: Any) -> dict[str, int | None] | None:
        role_map = self._custom_spells.get(role_key)
        if not isinstance(role_map, dict):
            return None
        entry = role_map.get(str(champ_id))
        return entry if isinstance(entry, dict) else None

    def set_spells(
        self,
        role_key: str,
        champ_id: Any,
        spell1_id: int | None,
        spell2_id: int | None,
        *,
        notify: bool = True,
    ) -> None:
        """
        Stores a spell pair.

        `notify=False` is for writes that only fill in defaults while rendering a row;
        emitting there would save the config on every tab redraw.
        """
        self._custom_spells.setdefault(role_key, {})[str(champ_id)] = {
            "spell1Id": spell1_id,
            "spell2Id": spell2_id,
        }
        if notify:
            self.changed.emit()


def _clone_page(page: dict) -> dict:
    """Shallow copy with the perk list copied too, so the dialog cannot mutate ours."""
    cloned = dict(page or {})
    perk_ids = cloned.get("selectedPerkIds")
    if isinstance(perk_ids, list):
        cloned["selectedPerkIds"] = list(perk_ids)
    return cloned
