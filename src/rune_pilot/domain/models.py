"""RunePilot data models — Pydantic-based automation configuration."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from rune_pilot.domain.champion_service import ensure_unique_role_champions
from rune_pilot.domain.rune_selection import clean_role_rune_selection


class AutomationConfig(BaseModel):
    """Automation settings received from the GUI."""

    primary_role: str | None = None
    secondary_role: str | None = None
    primary_summoner_spell: str | int | None = None
    secondary_summoner_spell: str | int | None = None
    role_summoner_spells: dict[str, dict[str, int | None]] = Field(default_factory=dict)
    # role -> champId(str) -> {"spell1Id": int|None, "spell2Id": int|None}
    custom_summoner_spells: dict[str, dict[str, dict[str, int | None]]] = Field(
        default_factory=dict
    )
    queue_id: int = 420
    role_champions: dict[str, list[int]] = Field(default_factory=dict)
    role_bans: dict[str, int] = Field(default_factory=dict)
    # champId(str) -> slot(str: "1"|"2"|"3") -> rune page dict
    custom_runes: dict[str, dict[str, dict]] = Field(default_factory=dict)
    # champId(str) -> 0(recommended) | 1 | 2 | 3
    rune_selection: dict[str, int] = Field(default_factory=dict)
    role_rune_selection: dict[str, dict[str, int]] = Field(default_factory=dict)
    # role -> champId(str) -> skinId(int)
    custom_skins: dict[str, dict[str, int]] = Field(default_factory=dict)
    auto_queue: bool = True

    @field_validator("role_rune_selection", mode="before")
    @classmethod
    def normalize_rune_assignments(cls, value):
        return clean_role_rune_selection(value)

    @field_validator("role_champions")
    @classmethod
    def unique_choices_per_role(cls, value: dict[str, list[int]]) -> dict[str, list[int]]:
        ensure_unique_role_champions(value)
        return value
