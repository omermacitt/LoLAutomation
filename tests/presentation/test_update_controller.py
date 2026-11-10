"""Update requests stay off Qt's thread and ignore results after closing."""

import threading
from unittest.mock import Mock

import pytest

from rune_pilot.domain.update import UpdateDownload, UpdateInfo
from rune_pilot.presentation.api_client import ApiError
from rune_pilot.presentation.controllers.update_controller import UpdateController


def offer():
    return UpdateInfo(
        update_id="known-id",
        latest_version="2",
        asset_download_url="https://github.com/test/app/Setup.exe",
    )


def test_check_runs_in_background_and_only_schedules_once(qt_app, wait_until):
    api = Mock()
    threads = []

    def check():
        threads.append(threading.get_ident())
        return offer()

    api.check_update.side_effect = check
    controller = UpdateController(api_client=api)
    received = []
    controller.update_available.connect(received.append)
    controller.schedule_check()
    controller.schedule_check()
    assert controller._timer.isActive()
    controller._timer.stop()
    controller._check_async()
    controller._check_async()
    wait_until(lambda: bool(received))
    api.check_update.assert_called_once()
    assert threads[0] != threading.get_ident()
    assert received == [offer()]
    controller.shutdown()


@pytest.mark.parametrize("result", [None, ApiError("offline")])
def test_unavailable_checks_are_silent(qt_app, wait_until, result):
    api = Mock()
    if isinstance(result, Exception):
        api.check_update.side_effect = result
    else:
        api.check_update.return_value = result
    controller = UpdateController(api_client=api)
    received = []
    controller.update_available.connect(received.append)
    controller._check_async()
    wait_until(lambda: not controller._check.busy)
    assert received == []
    controller.shutdown()


def test_download_sends_only_registered_id_and_prevents_duplicate_requests(qt_app, wait_until):
    entered, release = threading.Event(), threading.Event()
    api = Mock()

    def download(update_id):
        assert update_id == "known-id"
        entered.set()
        assert release.wait(2)
        return UpdateDownload(installer_path="C:/temp/Setup.exe")

    api.download_update.side_effect = download
    controller = UpdateController(api_client=api)
    started, finished = [], []
    controller.download_started.connect(lambda: started.append(True))
    controller.download_finished.connect(lambda *args: finished.append(args))
    try:
        controller.download(offer())
        assert entered.wait(2)
        controller.download(offer())
        assert started == [True]
        release.set()
        wait_until(lambda: bool(finished))
        assert finished == [(True, "C:/temp/Setup.exe", "")]
        api.download_update.assert_called_once_with("known-id")
    finally:
        release.set()
        controller.shutdown()


def test_failure_allows_download_retry(qt_app, wait_until):
    api = Mock()
    api.download_update.side_effect = ApiError("failed")
    controller = UpdateController(api_client=api)
    results = []
    controller.download_finished.connect(lambda *args: results.append(args))
    controller.download(offer())
    wait_until(lambda: not controller._download.busy)
    assert results == [(False, "", "failed")]
    api.download_update.side_effect = None
    api.download_update.return_value = UpdateDownload(installer_path="C:/temp/Setup.exe")
    controller.download(offer())
    wait_until(lambda: len(results) == 2)
    assert results[1] == (True, "C:/temp/Setup.exe", "")
    controller.shutdown()


@pytest.mark.parametrize("operation", ["check", "download"])
def test_close_suppresses_late_results_and_stops_scheduled_timer(qt_app, wait_until, operation):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    api = Mock()

    def request(*args):
        entered.set()
        release.wait(2)
        finished.set()
        return (
            offer() if operation == "check" else UpdateDownload(installer_path="C:/temp/Setup.exe")
        )

    api.check_update.side_effect = api.download_update.side_effect = request
    controller = UpdateController(api_client=api)
    results = []
    controller.update_available.connect(results.append)
    controller.download_finished.connect(lambda *args: results.append(args))
    try:
        controller.schedule_check()
        if operation == "check":
            controller._check_async()
        else:
            controller.download(offer())
        assert entered.wait(2)
        controller.shutdown()
        assert not controller._timer.isActive()
        release.set()
        wait_until(finished.is_set)
        qt_app.processEvents()
        assert not results
    finally:
        release.set()
        controller.shutdown()


def test_release_without_asset_opens_page_without_download(qt_app, monkeypatch):
    api = Mock()
    controller = UpdateController(api_client=api)
    open_page = Mock()
    monkeypatch.setattr(controller, "open_release_page", open_page)
    info = UpdateInfo(release_html_url="https://github.com/test/app/releases")
    controller.download(info)
    open_page.assert_called_once_with(info)
    api.download_update.assert_not_called()
    controller.shutdown()
