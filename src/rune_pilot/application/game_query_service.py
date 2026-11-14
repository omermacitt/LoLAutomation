"""UI query use cases; external readers are supplied by composition."""

from collections.abc import Callable
from typing import Any

from rune_pilot.domain.champion_service import is_mode_champion_variant
from rune_pilot.domain.game_data import (
    ChampionCatalog,
    ChampionOption,
    GameflowStatus,
    RuneCatalog,
    SkinCatalog,
    SkinOption,
    SkinOptions,
)


class QueryUnavailable(RuntimeError):
    """League Client data is unavailable or malformed; keep the previous UI state."""


class GameQueryService:
    def __init__(
        self,
        *,
        champion_summary: Callable[[], list[dict[str, Any]]],
        owned_champions: Callable[[], list[dict[str, Any]]],
        gameflow_phase: Callable[[], str | None],
        skin_options: Callable[[int], SkinCatalog],
        perk_styles: Callable[[], list[dict[str, Any]]],
        perks: Callable[[], list[dict[str, Any]]],
        perk_icon: Callable[[str], bytes | None],
    ):
        self._champion_summary = champion_summary
        self._owned_champions = owned_champions
        self._gameflow_phase = gameflow_phase
        self._skin_options = skin_options
        self._perk_styles = perk_styles
        self._perks = perks
        self._perk_icon = perk_icon

    def champion_catalog(self) -> ChampionCatalog:
        try:
            all_champions = self._champion_options(self._champion_summary())
            pickable = self._champion_options(self._owned_champions(), owned_only=True)
            if not all_champions:
                raise ValueError("empty champion summary")
            return ChampionCatalog(all_champions=all_champions, pickable_champions=pickable)
        except Exception as e:
            raise QueryUnavailable("Could not load champions from League Client") from e

    @staticmethod
    def _champion_options(
        raw: list[dict[str, Any]], *, owned_only: bool = False
    ) -> list[ChampionOption]:
        result: dict[int, ChampionOption] = {}
        for champion in raw:
            if not isinstance(champion, dict) or is_mode_champion_variant(champion):
                continue
            try:
                cid = int(champion.get("id"))
            except (TypeError, ValueError):
                continue
            if cid <= 0:
                continue
            ownership = champion.get("ownership") or {}
            if (
                owned_only
                and isinstance(ownership, dict)
                and ownership.get("owned") is False
                and not champion.get("freeToPlay")
            ):
                continue
            result[cid] = ChampionOption(
                id=cid, name=str(champion.get("name") or champion.get("alias") or cid)
            )
        return sorted(result.values(), key=lambda item: item.name)

    def gameflow(self) -> GameflowStatus:
        try:
            return GameflowStatus(phase=self._gameflow_phase())
        except Exception as e:
            raise QueryUnavailable("Could not read game state from League Client") from e

    def skins(self, champion_id: int) -> SkinOptions:
        try:
            catalog = self._skin_options(champion_id)
            names, owned, parents = catalog.names, catalog.owned, catalog.chroma_parents
            base = champion_id * 1000
            available = {base} | {sid for sid in owned if base < sid < base + 1000}
            options = [SkinOption(id=base, name=f"Default ({names.get(base) or 'Default'})")]
            options += [
                SkinOption(
                    id=sid, name=names.get(sid) or f"Skin {sid}", parent_skin_id=parents.get(sid)
                )
                for sid in sorted(owned)
                if base < sid < base + 1000
                and (
                    sid not in parents
                    or (parents[sid] in available and parents[sid] not in parents)
                )
            ]
            return SkinOptions(champion_id=champion_id, skins=options)
        except Exception as e:
            raise QueryUnavailable("Could not load skins from League Client") from e

    def rune_catalog(self) -> RuneCatalog:
        try:
            styles, perks = self._perk_styles(), self._perks()
            if not styles or not perks:
                raise ValueError("empty rune data")
            return RuneCatalog(styles=styles, perks=perks)
        except Exception as e:
            raise QueryUnavailable("Could not load runes from League Client") from e

    def icon(self, perk_id: int) -> bytes | None:
        """Resolve only known perk icons; clients cannot supply arbitrary LCU paths."""
        try:
            candidates = self._perks()
            if not any(
                isinstance(perk, dict) and str(perk.get("id")) == str(perk_id)
                for perk in candidates
            ):
                candidates = self._perk_styles()
            for perk in candidates:
                if not isinstance(perk, dict) or str(perk.get("id")) != str(perk_id):
                    continue
                path = str(perk.get("iconPath") or perk.get("icon_path") or "").strip()
                if (
                    not path
                    or ":" in path
                    or ".." in path
                    or "\\" in path
                    or "?" in path
                    or "#" in path
                ):
                    return None
                if not path.startswith("/"):
                    path = "/lol-game-data/assets/v1/" + path
                if not path.startswith("/lol-game-data/assets/"):
                    return None
                return self._perk_icon(path)
            return None
        except Exception as e:
            raise QueryUnavailable("Could not load rune icon from League Client") from e
