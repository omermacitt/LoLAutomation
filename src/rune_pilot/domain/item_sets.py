"""Item-set documents and direct-stat normalization, independent of I/O."""

import re
from html import unescape
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ItemStats(BaseModel):
    ad: float = 0
    ap: float = 0
    hp: float = 0
    armor: float = 0
    mr: float = 0
    attack_speed: float = 0
    haste: float = 0


class BuilderItem(BaseModel):
    id: int = Field(gt=0)
    name: str
    price: int = Field(ge=0)
    stats: ItemStats
    tags: list[str]
    description: str


class BuilderChampion(BaseModel):
    id: int = Field(gt=0)
    name: str


class ItemCatalog(BaseModel):
    version: str
    champions: list[BuilderChampion]
    items: list[BuilderItem]


class ChampionItemStats(BaseModel):
    champion_id: int
    version: str
    base: ItemStats
    growth: ItemStats
    attack_speed_ratio: float = Field(gt=0)


class SetItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int = Field(gt=0)
    count: int = Field(default=1, ge=1, le=10)


class ItemBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=60)
    items: list[SetItem] = Field(default_factory=list, max_length=40)
    slots: list[int | None] | None = Field(default=None, min_length=6, max_length=6)


class ItemSet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    uid: str = Field(pattern=r"^runepilot-[a-f0-9-]{36}$")
    title: str = Field(min_length=1, max_length=60)
    champion_id: int | None = Field(default=None, gt=0)
    map_id: Literal[11] = 11
    blocks: list[ItemBlock] = Field(min_length=1, max_length=20)

    @field_validator("title")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Set title cannot be blank")
        return value.strip()


class ItemSetCollection(BaseModel):
    sets: list[ItemSet] = Field(default_factory=list, max_length=100)

    @field_validator("sets")
    @classmethod
    def unique(cls, sets: list[ItemSet]) -> list[ItemSet]:
        if len({s.uid for s in sets}) != len(sets):
            raise ValueError("Duplicate set identifiers")
        return sets


def direct_stats(raw: dict) -> ItemStats:
    """Read only the explicit <stats> block; passives and effects are excluded."""
    match = re.search(r"<stats>(.*?)</stats>", str(raw.get("description", "")), re.S)
    text = unescape(re.sub(r"<[^>]*>", " ", re.sub(r"<br\s*/?>", "\n", match[1]))) if match else ""
    values = {}
    for key, label in {
        "ad": "Attack Damage",
        "ap": "Ability Power",
        "hp": "Health",
        "armor": "Armor",
        "mr": "Magic Resist",
        "attack_speed": "Attack Speed",
        "haste": "Ability Haste",
    }.items():
        number = re.search(r"^\s*(\d+(?:\.\d+)?)\s*(%)?\s+" + label + r"\s*$", text, re.M)
        if number and (not number[2] or key == "attack_speed"):
            values[key] = float(number[1]) / (100 if number[2] else 1)
    return ItemStats(**values)


def league_set(item_set: ItemSet) -> dict:
    return {
        "uid": item_set.uid,
        "title": item_set.title,
        "type": "custom",
        "map": "SR",
        "mode": "any",
        "sortrank": 0,
        "startedFrom": "blank",
        "preferredItemSlots": [],
        "associatedChampions": [item_set.champion_id] if item_set.champion_id else [],
        "associatedMaps": [11],
        "blocks": [
            {
                "type": b.name,
                "hideIfSummonerSpell": "",
                "showIfSummonerSpell": "",
                "items": [{"id": str(i.id), "count": i.count} for i in b.items],
            }
            for b in item_set.blocks
        ],
    }
