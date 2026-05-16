"""RunePilot paylaşımlı yardımcı fonksiyonlar."""

from __future__ import annotations

from typing import Any


def safe_int_list(values: Any) -> list[int]:
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
