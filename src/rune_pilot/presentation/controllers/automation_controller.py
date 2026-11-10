"""
Drives the backend from the UI: health polling, start, stop, and live config pushes.

Holds the one piece of state that decides how the whole start/stop area of the window
looks — `checking`, `offline`, `stopped`, `running`, `starting` or `stopping` — and
emits it as `state_changed` rather than reaching into widgets itself. HTTP lives
entirely behind `ApiClient`; this class never sees a URL.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from rune_pilot.presentation.api_client import ApiClient, ApiError

HEALTH_POLL_MS = 4000
# Long enough to coalesce a burst of edits (dragging through a combo box) into one
# push, short enough that the running automation picks the change up right away.
LIVE_PUSH_DEBOUNCE_MS = 350

STATE_CHECKING = "checking"
STATE_OFFLINE = "offline"
STATE_STOPPED = "stopped"
STATE_RUNNING = "running"
STATE_STARTING = "starting"
STATE_STOPPING = "stopping"


class AutomationController(QObject):
    """Owns automation state and every call to the backend."""

    # (state, tooltip)
    state_changed = pyqtSignal(str, str)
    # (level: "info"|"error", title, message)
    notified = pyqtSignal(str, str, str)

    def __init__(
        self,
        payload_provider: Callable[[], dict[str, Any]],
        client: ApiClient | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._payload_provider = payload_provider
        self._client = client or ApiClient()
        self._state = STATE_CHECKING

        # A start or stop is in flight. Health results are ignored while it is, so a
        # poll that started before the click cannot overwrite the new state.
        self._action_inflight = False
        self._health_inflight = False

        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self.check_health)

        self._push_timer = QTimer(self)
        self._push_timer.setSingleShot(True)
        self._push_timer.timeout.connect(self._push_config)

        self._health_result = _HealthSignal()
        self._health_result.received.connect(self._on_health_received)

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state == STATE_RUNNING

    # -- health polling ------------------------------------------------------

    def start_polling(self, interval_ms: int = HEALTH_POLL_MS) -> None:
        self._health_timer.start(interval_ms)
        self.check_health()

    def stop_polling(self) -> None:
        self._health_timer.stop()

    def check_health(self) -> None:
        """Polls `/health` on a worker thread; the result arrives on the UI thread."""
        if self._action_inflight or self._health_inflight:
            return
        self._health_inflight = True

        def worker() -> None:
            status = self._client.health()
            self._health_result.received.emit(status.ok, status.running, status.error)

        threading.Thread(target=worker, daemon=True).start()

    def _on_health_received(self, ok: bool, running: bool, error: str) -> None:
        self._health_inflight = False
        if self._action_inflight:
            return
        if not ok:
            self._set_state(STATE_OFFLINE, error or "")
            return
        self._set_state(STATE_RUNNING if running else STATE_STOPPED, "Server running")

    # -- start / stop --------------------------------------------------------

    def request_start(self) -> None:
        """
        Starts the automation with the current UI selections.

        Runs on the UI thread: it is a click with a short timeout, and the window is
        meant to be inert until the backend answers.
        """
        if self._action_inflight:
            return

        self._action_inflight = True
        self._set_state(STATE_STARTING)
        try:
            status = self._client.health()
            if not status.ok:
                self._set_state(STATE_OFFLINE)
                self.notified.emit(
                    "error",
                    "Server Not Running",
                    "Could not connect to the backend. Make sure you launched the app "
                    f"via run_app.py or the packaged executable.\n\nDetail: {status.error}",
                )
                return

            self._client.start_automation(self._payload_provider())
            self._set_state(STATE_RUNNING)
            self.notified.emit("info", "Success", "RunePilot started!")
        except ApiError as e:
            self._set_state(STATE_OFFLINE)
            self.notified.emit("error", "Error", f"Failed to start:\n{e}")
        except Exception as e:
            self._set_state(STATE_OFFLINE)
            self.notified.emit("error", "Error", f"Failed to build the automation config:\n{e}")
        finally:
            self._action_inflight = False
            self.check_health()

    def request_stop(self) -> None:
        if self._action_inflight:
            return

        self._action_inflight = True
        self._set_state(STATE_STOPPING)
        try:
            self._client.stop_automation()
            self._set_state(STATE_STOPPED)
            self.notified.emit("info", "Stopped", "RunePilot stopped.")
        except ApiError as e:
            self._set_state(STATE_OFFLINE)
            self.notified.emit("error", "Error", f"Could not stop RunePilot: {e}")
        finally:
            self._action_inflight = False
            self.check_health()

    # -- live config push ----------------------------------------------------

    def schedule_config_push(self) -> None:
        """
        Queues a config push to a running automation, debounced.

        Does nothing unless the automation is actually running — while it is stopped
        the config is only read at the next start.
        """
        if self._state != STATE_RUNNING or self._action_inflight:
            return
        self._push_timer.start(LIVE_PUSH_DEBOUNCE_MS)

    def _push_config(self) -> None:
        if self._state != STATE_RUNNING or self._action_inflight:
            return

        try:
            payload = self._payload_provider()
        except Exception as e:
            print(f"[CONFIG] Payload build failed: {e}")
            return

        def worker() -> None:
            try:
                self._client.start_automation(payload)
            except ApiError as e:
                # Nothing to show the user: the automation keeps running on its previous
                # config, and the next edit or health poll will surface a real outage.
                print(f"[CONFIG] Live update failed: {e}")

        threading.Thread(target=worker, daemon=True).start()

    # -- internals -----------------------------------------------------------

    def _set_state(self, state: str, tooltip: str = "") -> None:
        self._state = state
        self.state_changed.emit(state, tooltip)


class _HealthSignal(QObject):
    """Carries a worker thread's health result back to the UI thread."""

    received = pyqtSignal(bool, bool, str)
