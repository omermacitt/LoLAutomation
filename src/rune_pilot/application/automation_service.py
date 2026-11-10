"""Serial automation worker lifecycle with independent cancellation per run."""

from __future__ import annotations

import threading
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from rune_pilot.application.automation_state import AutomationSnapshot
from rune_pilot.domain.champion_service import ensure_unique_role_champions

LoopFn = Callable[
    [Callable[[], bool], Callable[[], AutomationSnapshot], Callable[[float], bool]],
    None,
]


class AutomationService:
    def __init__(self, loop: LoopFn) -> None:
        self._loop = loop
        self._lock = threading.Lock()
        self._running = False
        self._closed = False
        self._revision = 0
        self._config: dict[str, Any] = {}
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_error: str | None = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def config(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._config)

    @property
    def last_error(self) -> str | None:
        with self._lock:
            return self._last_error

    def _snapshot(self) -> AutomationSnapshot:
        with self._lock:
            return AutomationSnapshot(self._revision, deepcopy(self._config))

    def start(self, config: dict[str, Any]) -> str:
        ensure_unique_role_champions(config.get("role_champions", {}))
        settings = deepcopy(config)
        settings.pop("runes_applied", None)
        settings.pop("skin_applied_key", None)
        with self._lock:
            if self._closed:
                raise RuntimeError("Automation service is shutting down")
            already_running = self._running
            self._config = settings
            self._revision += 1
            self._running = True
            self._last_error = None
            if self._thread is None:
                self._stop_event = threading.Event()
                self._thread = threading.Thread(
                    target=self._run,
                    args=(self._stop_event,),
                    name="rune-pilot-automation",
                    daemon=True,
                )
                self._thread.start()
            # If Stop is still finishing, the same worker starts a fresh invocation
            # after the old invocation returns. Its cancelled event stays cancelled.
        return "updated" if already_running else "started"

    def stop(self) -> None:
        with self._lock:
            self._running = False
            self._stop_event.set()

    def update_running(self, config: dict[str, Any]) -> bool:
        """Update a live invocation only; never restart after Stop or loop exit."""
        ensure_unique_role_champions(config.get("role_champions", {}))
        settings = deepcopy(config)
        settings.pop("runes_applied", None)
        settings.pop("skin_applied_key", None)
        with self._lock:
            if self._closed or not self._running:
                return False
            self._config = settings
            self._revision += 1
            return True

    def shutdown(self, timeout: float = 10.0) -> bool:
        with self._lock:
            self._closed = True
            self._running = False
            self._stop_event.set()
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)
        return thread is None or not thread.is_alive()

    def _run(self, stop_event: threading.Event) -> None:
        while True:
            error = None
            try:
                self._loop(
                    lambda event=stop_event: not event.is_set(), self._snapshot, stop_event.wait
                )
            except Exception as failure:
                error = type(failure).__name__
            with self._lock:
                # A requested restart may proceed only after the old loop ended.
                if stop_event.is_set() and self._running and not self._closed:
                    stop_event = threading.Event()
                    self._stop_event = stop_event
                    continue
                self._last_error = error
                self._running = False
                self._thread = None
                return
