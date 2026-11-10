"""Startup protection, serialized saves, snapshots and save retries."""

import threading

import pytest

from rune_pilot.domain.user_config import UserConfig
from rune_pilot.presentation.api_client import ApiError
from rune_pilot.presentation.controllers import settings_controller as module


class RecordingApi:
    def __init__(self):
        self.config = UserConfig(queue_name="Ranked Flex")
        self.loads = 0
        self.load_failures = 0
        self.save_failures = 0
        self.save_error = "save failed"
        self.save_started = threading.Event()
        self.release_save = threading.Event()
        self.release_save.set()
        self.writes = []
        self.successful_writes = []
        self.worker_threads = []

    def load_settings(self):
        self.worker_threads.append(threading.get_ident())
        self.loads += 1
        if self.loads <= self.load_failures:
            raise ApiError("backend starting")
        return self.config.model_copy(deep=True)

    def save_settings(self, config):
        self.worker_threads.append(threading.get_ident())
        self.writes.append(config.model_copy(deep=True))
        self.save_started.set()
        if not self.release_save.wait(3):
            raise ApiError("test save gate timed out")
        if len(self.writes) <= self.save_failures:
            raise ApiError(self.save_error)
        self.config = config.model_copy(deep=True)
        self.successful_writes.append(config.model_copy(deep=True))
        return config


@pytest.fixture
def controller(qt_app, monkeypatch):
    monkeypatch.setattr(module, "RETRY_MS", 20)
    monkeypatch.setattr(module, "SAVE_DEBOUNCE_MS", 10)
    api = RecordingApi()
    controller = module.SettingsController(api)
    yield controller, api
    api.release_save.set()
    controller.shutdown()


def test_no_writes_before_load_and_startup_failure_retries(controller, wait_until):
    settings, api = controller
    api.load_failures = 1
    loaded = []
    errors = []
    settings.loaded.connect(loaded.append)
    settings.failed.connect(errors.append)
    assert settings.save(UserConfig()) is False
    settings.load()
    wait_until(lambda: settings.ready)
    assert errors == ["backend starting"]
    assert loaded == [UserConfig(queue_name="Ranked Flex")]
    assert not api.writes
    assert api.loads == 2
    settings.load()
    assert api.loads == 2  # Reload cannot clobber edits after initialization.


def test_saves_are_sequential_coalesced_and_detached_from_ui_data(controller, wait_until):
    settings, api = controller
    settings.load()
    wait_until(lambda: settings.ready)
    api.release_save.clear()
    saved = []
    settings.saved.connect(lambda: saved.append(True))
    first = UserConfig(queue_name="first", role_champions_ui={"TOP": [1]})
    settings.save(first)
    first.role_champions_ui["TOP"].append(2)
    settings.flush()
    wait_until(api.save_started.is_set)
    settings.save(UserConfig(queue_name="second"))
    settings.save(UserConfig(queue_name="latest"))
    settings.flush()
    assert len(api.writes) == 1
    # Timers/signals continue to run while the worker is waiting for HTTP.
    assert not saved
    api.release_save.set()
    wait_until(lambda: bool(saved))
    assert [config.queue_name for config in api.writes] == ["first", "latest"]
    assert api.writes[0].role_champions_ui == {"TOP": [1]}
    assert api.config.queue_name == "latest"
    assert all(thread != threading.get_ident() for thread in api.worker_threads)


def test_failed_save_retries_latest_edit_instead_of_stale_snapshot(controller, wait_until):
    settings, api = controller
    api.save_failures = 1
    settings.load()
    wait_until(lambda: settings.ready)
    api.release_save.clear()
    errors = []
    saved = []
    settings.failed.connect(errors.append)
    settings.saved.connect(lambda: saved.append(True))
    settings.save(UserConfig(queue_name="old"))
    settings.flush()
    wait_until(api.save_started.is_set)
    settings.save(UserConfig(queue_name="new"))
    api.release_save.set()
    wait_until(lambda: bool(saved))
    assert errors == ["save failed"]
    assert [config.queue_name for config in api.writes] == ["old", "new"]
    assert [config.queue_name for config in api.successful_writes] == ["new"]


def test_exception_with_empty_message_is_not_a_successful_save(controller, wait_until):
    settings, api = controller
    api.save_failures = 1
    api.save_error = ""
    settings.load()
    wait_until(lambda: settings.ready)
    errors = []
    saved = []
    settings.failed.connect(errors.append)
    settings.saved.connect(lambda: saved.append(True))
    settings.save(UserConfig(queue_name="retry me"))
    settings.flush()
    wait_until(lambda: bool(saved))
    assert errors == ["ApiError"]
    assert len(api.writes) == 2
    assert len(api.successful_writes) == 1
