"""Automation lifecycle: start, live config swap, stop.

Runs against a stub loop, so none of this needs a League Client — the point of moving
the state off module-level globals and onto an injectable service.
"""

from __future__ import annotations

import threading
import time
import pytest

from rune_pilot.application.automation_service import AutomationService


class RecordingLoop:
    """A stand-in for `automation_loop` that records the configs it was given."""

    def __init__(self) -> None:
        self.seen: list[dict] = []
        self.started = threading.Event()
        self.finished = threading.Event()

    def __call__(self, should_run, get_snapshot, wait) -> None:
        self.started.set()
        while should_run():
            self.seen.append(dict(get_snapshot().config))
            wait(0.005)
        self.finished.set()

    def wait_for_config(self, predicate, timeout: float = 2.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if any(predicate(config) for config in list(self.seen)):
                return True
            time.sleep(0.005)
        return False


def test_starts_not_running():
    assert AutomationService(loop=RecordingLoop()).is_running is False


def test_start_then_stop():
    loop = RecordingLoop()
    service = AutomationService(loop=loop)

    assert service.start({"queue_id": 420}) == "started"
    assert loop.started.wait(timeout=2.0)
    assert service.is_running is True

    service.stop()
    assert loop.finished.wait(timeout=2.0)
    assert service.is_running is False


def test_second_start_updates_instead_of_starting_again():
    loop = RecordingLoop()
    service = AutomationService(loop=loop)
    try:
        assert service.start({"queue_id": 420}) == "started"
        assert loop.started.wait(timeout=2.0)
        assert service.start({"queue_id": 440}) == "updated"

        # The running loop must pick the new config up rather than hold the old one.
        assert loop.wait_for_config(lambda config: config.get("queue_id") == 440)
    finally:
        service.stop()


def test_config_and_snapshots_are_defensive_and_revision_advances_on_same_values():
    service = AutomationService(loop=RecordingLoop())
    original = {"role_champions": {"TOP": [1]}, "runes_applied": True, "skin_applied_key": "1:1001"}
    try:
        service.start(original)
        first = service._snapshot()
        original["role_champions"]["TOP"].clear()
        first.config["role_champions"]["TOP"].append(2)
        service.config["role_champions"]["TOP"].clear()
        assert service.config == {"role_champions": {"TOP": [1]}}
        service.start(service.config)
        assert service._snapshot().revision == first.revision + 1
    finally:
        assert service.shutdown()


def test_stop_is_safe_when_never_started():
    service = AutomationService(loop=RecordingLoop())
    service.stop()
    assert service.is_running is False


def test_restart_after_stop_starts_a_fresh_run():
    loop = RecordingLoop()
    service = AutomationService(loop=loop)

    service.start({"queue_id": 420})
    assert loop.started.wait(timeout=2.0)
    service.stop()
    assert loop.finished.wait(timeout=2.0)

    loop.started.clear()
    assert service.start({"queue_id": 440}) == "started"
    assert loop.started.wait(timeout=2.0)
    assert service.shutdown()


def test_rapid_stop_start_waits_for_old_loop_and_never_revives_its_signal():
    entered = threading.Event()
    release_old = threading.Event()
    restarted = threading.Event()
    observed = []
    signals = []
    active = 0
    calls = 0
    lock = threading.Lock()

    def loop(should_run, get_snapshot, wait):
        nonlocal calls, active
        signals.append(should_run)
        with lock:
            calls += 1
            active += 1
            assert active == 1
            invocation = calls
        try:
            if invocation == 1:
                entered.set()
                assert release_old.wait(2)
                observed.append(should_run())
            else:
                observed.append(get_snapshot().config["queue_id"])
                restarted.set()
                while should_run():
                    wait(1)
        finally:
            with lock:
                active -= 1

    service = AutomationService(loop)
    try:
        service.start({"queue_id": 420})
        assert entered.wait(2)
        service.stop()
        assert service.start({"queue_id": 440}) == "started"
        assert service.start({"queue_id": 450}) == "updated"
        assert calls == 1
        release_old.set()
        assert restarted.wait(2)
        assert observed == [False, 450]
        assert calls == 2
        assert not signals[0]()  # Old callbacks stay cancelled after replacement.
        assert signals[1]()
    finally:
        release_old.set()
        assert service.shutdown()


def test_shutdown_interrupts_sleep_and_prevents_future_starts():
    entered = threading.Event()
    finished = threading.Event()
    def loop(should_run, get_snapshot, wait):
        entered.set()
        wait(100)
        assert not should_run()
        finished.set()
    service = AutomationService(loop)
    service.start({"queue_id": 420})
    assert entered.wait(2)
    assert service.shutdown(timeout=1)
    assert finished.is_set()
    with pytest.raises(RuntimeError, match="shutting down"):
        service.start({})


def test_loop_failure_clears_running_state_and_allows_a_fresh_start():
    def broken(*args):
        raise ValueError("failure")
    service = AutomationService(broken)
    service.start({"queue_id": 420})
    thread = service._thread
    if thread is not None:
        thread.join(2)
    assert not service.is_running
    assert service.last_error == "ValueError"
    loop = RecordingLoop()
    service._loop = loop
    assert service.start({"queue_id": 440}) == "started"
    assert loop.started.wait(2)
    assert service.last_error is None
    assert service.shutdown()


def test_shutdown_timeout_reports_pending_io_and_cancellation_remains_set():
    entered, release = threading.Event(), threading.Event()
    def loop(should_run, get_snapshot, wait):
        entered.set()
        release.wait(2)
        assert not should_run()
    service = AutomationService(loop)
    service.start({})
    try:
        assert entered.wait(2)
        assert not service.shutdown(timeout=0)
        assert not service.is_running
    finally:
        release.set()
        assert service.shutdown(timeout=2)
