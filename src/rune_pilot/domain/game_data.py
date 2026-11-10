"""Validated data contracts shared by HTTP routes and desktop clients."""

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


class SkinOptions(BaseModel):
    champion_id: int = Field(gt=0)
    skins: list[SkinOption] = Field(min_length=1)


class RuneCatalog(BaseModel):
    styles: list[dict[str, Any]] = Field(min_length=1)
    perks: list[dict[str, Any]] = Field(min_length=1)
