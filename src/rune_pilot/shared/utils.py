"""RunePilot shared utility functions."""

from __future__ import annotations

from typing import Any


def safe_int_list(values: Any) -> list[int]:
    """Converts list values to int, silently skipping values that cannot be converted."""
    result: list[int] = []
    if not isinstance(values, list):
        return result
    for v in values:
        try:
            result.append(int(v))
        except (TypeError, ValueError):
            continue
    return result
