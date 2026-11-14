"""Validated data contracts shared by HTTP routes and desktop clients."""

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


class ChampionOption(BaseModel):
    id: int = Field(gt=0)
    name: str


class ChampionCatalog(BaseModel):
    all_champions: list[ChampionOption] = Field(min_length=1)
    pickable_champions: list[ChampionOption]


class GameflowStatus(BaseModel):
    phase: str | None


class SkinOption(BaseModel):
    id: int = Field(ge=0)
    name: str
    parent_skin_id: int | None = Field(default=None, gt=0)


@dataclass
class SkinCatalog:
    names: dict[int, str]
    owned: set[int]
    chroma_parents: dict[int, int] = field(default_factory=dict)


class SkinOptions(BaseModel):
    champion_id: int = Field(gt=0)
    skins: list[SkinOption] = Field(min_length=1)


class RuneCatalog(BaseModel):
    styles: list[dict[str, Any]] = Field(min_length=1)
    perks: list[dict[str, Any]] = Field(min_length=1)
