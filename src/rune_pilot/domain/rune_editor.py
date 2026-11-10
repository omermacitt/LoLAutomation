"""Pure normalization and validation for the visual rune editor."""

from html.parser import HTMLParser
from typing import Any, Literal

from pydantic import BaseModel, Field

MAIN_STYLES = {8000, 8100, 8200, 8300, 8400}


class RuneChoice(BaseModel):
    id: int = Field(gt=0)
    name: str
    description: str = ""


class RuneEditorStyle(BaseModel):
    id: int = Field(gt=0)
    name: str
    description: str = ""
    allowedSubStyles: list[int]
    rows: list[list[RuneChoice]] = Field(min_length=4, max_length=4)
    shardRows: list[list[RuneChoice]] = Field(min_length=3, max_length=3)


class RuneEditorCatalog(BaseModel):
    styles: list[RuneEditorStyle] = Field(min_length=2)


class RunePage(BaseModel):
    name: str = Field(default="Custom", min_length=1, max_length=16)
    primaryStyleId: int = Field(gt=0)
    subStyleId: int = Field(gt=0)
    selectedPerkIds: list[int] = Field(min_length=9, max_length=9)


class RuneRecommendation(BaseModel):
    champion_id: int
    source: Literal["bundled"] = "bundled"
    page: RunePage | None = None
    unavailableReason: Literal["missing", "outdated"] | None = None


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in {"br", "p", "div", "li"}:
            self.parts.append(" ")


def _text(value: Any) -> str:
    parser = _PlainText()
    parser.feed(str(value or ""))
    return " ".join("".join(parser.parts).split())[:4000]


def _id(value: Any) -> int | None:
    try:
        result = int(value)
        return result if result > 0 else None
    except (TypeError, ValueError):
        return None


def _slots(style: dict) -> list:
    for key in ("slots", "perkSlots", "runeSlots"):
        if isinstance(style.get(key), list):
            return style[key]
    return []


def normalize_editor_catalog(styles: list[dict], perks: list[dict]) -> RuneEditorCatalog:
    lookup = {_id(perk.get("id")): perk for perk in perks if isinstance(perk, dict)}

    def row(slot: Any) -> list[RuneChoice]:
        if not isinstance(slot, dict):
            return []
        values = next((slot[key] for key in ("runes", "perks", "perkIds", "runeIds") if isinstance(slot.get(key), list)), [])
        result: dict[int, RuneChoice] = {}
        for value in values:
            embedded = value if isinstance(value, dict) else {}
            rid = _id(embedded.get("id") or embedded.get("perkId") or embedded.get("runeId") or (value if not embedded else None))
            if rid is None:
                continue
            metadata = {**lookup.get(rid, {}), **embedded}
            result[rid] = RuneChoice(id=rid,
                name=_text(metadata.get("name") or metadata.get("displayName") or metadata.get("perkName") or rid),
                description=_text(metadata.get("longDesc") or metadata.get("shortDesc") or metadata.get("tooltip")))
        return list(result.values())

    stat_style = next((style for style in styles if isinstance(style, dict) and _id(style.get("id")) == 5000), None)
    normalized: list[RuneEditorStyle] = []
    for style in styles:
        if not isinstance(style, dict) or _id(style.get("id")) not in MAIN_STYLES:
            continue
        sid = int(style["id"])
        slots = _slots(style)
        stat_slots = [slot for slot in slots if isinstance(slot, dict) and "statmod" in str(slot.get("type", "")).lower()]
        primary_slots = [slot for slot in slots if slot not in stat_slots][:4]
        if len(stat_slots) < 3:
            stat_slots = _slots(stat_style) if stat_style else slots[4:7]
        rows, shards = [row(slot) for slot in primary_slots], [row(slot) for slot in stat_slots[:3]]
        if len(rows) != 4 or len(shards) != 3 or not all(rows + shards):
            raise ValueError("Rune slot metadata is incomplete")
        allowed = style.get("allowedSubStyles")
        allowed_ids = [_id(value) for value in allowed] if isinstance(allowed, list) else list(MAIN_STYLES - {sid})
        normalized.append(RuneEditorStyle(id=sid, name=_text(style.get("name") or sid), description=_text(style.get("tooltip")),
            allowedSubStyles=[value for value in allowed_ids if value in MAIN_STYLES and value != sid], rows=rows, shardRows=shards))
    available = {style.id for style in normalized}
    for style in normalized:
        style.allowedSubStyles = [sid for sid in style.allowedSubStyles if sid in available]
        if not style.allowedSubStyles:
            raise ValueError("No compatible secondary style")
    return RuneEditorCatalog(styles=normalized)


def validate_editor_page(page: RunePage, catalog: RuneEditorCatalog) -> RunePage:
    styles = {style.id: style for style in catalog.styles}
    primary, secondary = styles.get(page.primaryStyleId), styles.get(page.subStyleId)
    if not primary or not secondary or page.subStyleId not in primary.allowedSubStyles:
        raise ValueError("Primary and secondary styles must be different and compatible")
    ids = page.selectedPerkIds
    if any(ids[index] not in {perk.id for perk in row} for index, row in enumerate(primary.rows)):
        raise ValueError("Choose one rune from every primary row")
    secondary_rows = [next((index for index, row in enumerate(secondary.rows[1:], 1) if rid in {perk.id for perk in row}), None) for rid in ids[4:6]]
    if None in secondary_rows or len(set(secondary_rows)) != 2:
        raise ValueError("Secondary runes must come from two different non-keystone rows")
    # Shards may legally repeat across different rows (for example 5008 / 5008).
    if any(ids[index + 6] not in {perk.id for perk in row} for index, row in enumerate(primary.shardRows)):
        raise ValueError("Choose one stat shard from every row")
    return page
