"""Recommendation data source; file access belongs to its infrastructure adapter."""

from typing import Any, Protocol


class RuneDataSource(Protocol):
    def get_runes_data(self) -> dict[str, Any]: ...
