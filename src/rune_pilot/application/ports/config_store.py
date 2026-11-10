"""Storage contract for the settings document."""

from collections.abc import Callable
from typing import Any, Protocol


class ConfigStore(Protocol):
    def read(self) -> dict[str, Any]:
        """Read the document, including keys owned by other use cases."""
        ...

    def update(self, mutate: Callable[[dict[str, Any]], None]) -> bool:
        """Atomically re-read/mutate/persist; a raised mutation must not write."""
        ...
