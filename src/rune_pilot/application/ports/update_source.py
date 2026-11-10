"""Backend release discovery and local installer storage contract."""

from typing import Protocol

from rune_pilot.domain.update import UpdateInfo


class UpdateSource(Protocol):
    def latest_release(self) -> dict | None: ...
    def download(self, info: UpdateInfo) -> str: ...
