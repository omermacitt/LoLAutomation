"""
RunePilot rün servisi.

Rün sayfası önerisi, isim oluşturma ve rün verisi işleme.
"""

from __future__ import annotations

import re
from typing import Any

from src.rune_pilot.domain.constants import STYLE_ID_BY_NAME, MAX_RUNE_PAGE_NAME_LEN
from src.rune_pilot.domain.champion_service import get_champion_slug_by_id
from src.rune_pilot.infrastructure.rune_data_provider import get_runes_data


def _safe_int_list(values: Any) -> list[int]:
    """Liste içindeki değerleri int'e çevirir; çevrilemeyenleri atlar."""
    result: list[int] = []
    if not isinstance(values, list):
        return result
    for v in values:
        try:
            result.append(int(v))
        except (TypeError, ValueError):
            continue
    return result


def build_rune_page_name(*, prefix: str, champion_name: str) -> str:
    """LoL client rune sayfası isim limitine göre güvenli bir isim üretir."""
    prefix = (prefix or "").strip() or "Auto"
    champ = (champion_name or "").strip() or "Champion"

    # Prefer a compact (no spaces/punctuation) champion name to fit the client limit.
    champ_compact = re.sub(r"[^0-9A-Za-z]", "", champ)
    champ_base = champ_compact or champ

    # Prefer "Prefix Champion" then "Prefix-Champion", then truncate champion name.
    candidate = f"{prefix} {champ_base}"
    if len(candidate) <= MAX_RUNE_PAGE_NAME_LEN:
        return candidate

    candidate = f"{prefix}-{champ_base}"
    if len(candidate) <= MAX_RUNE_PAGE_NAME_LEN:
        return candidate

    sep = " "
    max_champ_len = MAX_RUNE_PAGE_NAME_LEN - (len(prefix) + len(sep))
    if max_champ_len <= 0:
        return prefix[:MAX_RUNE_PAGE_NAME_LEN]
    champ_trunc = champ_base[:max_champ_len]
    return f"{prefix}{sep}{champ_trunc}"


def get_recommended_page_for_champion(champ_id: int) -> dict | None:
    """
    Supports 2 formats:
    1) { "123": {"primaryStyleId":..., "subStyleId":..., "selectedPerkIds":[...]}, ... }
    2) { "annie": {"rune_1": {"Domination":[...], "Sorcery":[...], "Shards":[...]}, ...}, ... }
    """
    runes_data = get_runes_data()

    # Format 1: direct champId -> payload
    direct = runes_data.get(str(champ_id))
    if isinstance(direct, dict) and "primaryStyleId" in direct and "subStyleId" in direct and "selectedPerkIds" in direct:
        try:
            primary_style_id = int(direct.get("primaryStyleId"))
            sub_style_id = int(direct.get("subStyleId"))
        except (TypeError, ValueError):
            return None

        selected = _safe_int_list(direct.get("selectedPerkIds"))
        if len(selected) != 9:
            return None

        return {"primaryStyleId": primary_style_id, "subStyleId": sub_style_id, "selectedPerkIds": selected}

    # Format 2: slug -> rune_1 -> tree lists
    slug = get_champion_slug_by_id(champ_id)
    if not slug:
        return None
    champ_blob = runes_data.get(slug)
    if not isinstance(champ_blob, dict):
        return None

    def _parse_win_rate(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        if not s:
            return None
        s = s.replace(",", ".")
        m = re.search(r"(\d+(?:\.\d+)?)", s)
        if not m:
            return None
        try:
            return float(m.group(1))
        except ValueError:
            return None

    rune_candidates: list[tuple[float, str, dict]] = []
    default_blob: dict | None = None
    fallback_blob: dict | None = None

    for k, v in champ_blob.items():
        if not (isinstance(k, str) and k.startswith("rune_") and isinstance(v, dict)):
            continue
        if fallback_blob is None:
            fallback_blob = v
        if k == "rune_1":
            default_blob = v

        win_rate = (
            v.get("Win Rate")
            or v.get("win_rate")
            or v.get("WinRate")
            or v.get("winRate")
            or v.get("WIN RATE")
        )
        parsed_wr = _parse_win_rate(win_rate)
        if parsed_wr is None:
            parsed_wr = -1.0
        rune_candidates.append((parsed_wr, k, v))

    if not rune_candidates:
        return None

    # Sort by winrate desc, then by rune_* key for stability.
    rune_candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)

    def _convert_blob_to_page(rune_blob: dict) -> dict | None:
        style_entries: list[tuple[str, int, int]] = []
        for k, v in rune_blob.items():
            if not isinstance(k, str):
                continue
            style_id = STYLE_ID_BY_NAME.get(k.strip().lower())
            if style_id is None:
                continue
            if not isinstance(v, list):
                continue
            style_entries.append((k, style_id, len(v)))

        if len(style_entries) < 2:
            return None

        primary_key = next((k for k, _sid, ln in style_entries if ln == 4), style_entries[0][0])
        secondary_key = next(
            (k for k, _sid, ln in style_entries if ln == 2 and k != primary_key),
            style_entries[1][0] if style_entries[1][0] != primary_key else style_entries[0][0],
        )

        primary_style_id = STYLE_ID_BY_NAME.get(primary_key.strip().lower())
        secondary_style_id = STYLE_ID_BY_NAME.get(secondary_key.strip().lower())
        if primary_style_id is None or secondary_style_id is None:
            return None

        primary_ids = _safe_int_list(rune_blob.get(primary_key))
        secondary_ids = _safe_int_list(rune_blob.get(secondary_key))

        shards_ids: list[int] = []
        for k, v in rune_blob.items():
            if isinstance(k, str) and k.strip().lower() == "shards":
                shards_ids = _safe_int_list(v)
                break

        selected = primary_ids[:4] + secondary_ids[:2] + shards_ids[:3]
        if len(selected) != 9:
            return None

        return {
            "primaryStyleId": primary_style_id,
            "subStyleId": secondary_style_id,
            "selectedPerkIds": selected,
        }

    # Try highest winrate first; if conversion fails, fall back to rune_1 then first available.
    for _wr, _name, blob in rune_candidates:
        page = _convert_blob_to_page(blob)
        if page:
            if _wr >= 0:
                print(f"[RUNES] Recommended rune selected: {slug}:{_name} winRate={_wr}")
            else:
                print(f"[RUNES] Recommended rune selected: {slug}:{_name}")
            return page

    if default_blob is not None:
        page = _convert_blob_to_page(default_blob)
        if page:
            return page

    if fallback_blob is not None:
        page = _convert_blob_to_page(fallback_blob)
        if page:
            return page

    return None
