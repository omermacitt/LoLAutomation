"""Versioned settings snapshots and worker-owned progress, separate from settings."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AutomationSnapshot:
    revision: int
    config: dict[str, Any]


@dataclass
class AutomationProgress:
    revision: int = -1
    rune_champion: int | None = None
    skin_key: tuple[int, int] | None = None

    def reset(self, revision: int) -> None:
        self.revision = revision
        self.rune_champion = None
        self.skin_key = None
