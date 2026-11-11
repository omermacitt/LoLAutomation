"""Public selection feedback; never contains raw League replies or settings."""

from typing import Literal

from pydantic import BaseModel


class SelectionNotice(BaseModel):
    id: int
    code: Literal[
        "no_preference",
        "all_unavailable",
        "pick_failed",
        "manual_hover",
        "rune_fallback",
        "rune_unavailable",
    ]
    role: str
    champion_id: int | None = None
