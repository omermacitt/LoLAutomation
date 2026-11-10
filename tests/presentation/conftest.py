"""Headless Qt event loop for controller and window integration checks."""

import gc
import os
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent
from PyQt6.QtWidgets import QApplication

# Keep the application alive until all Qt wrappers have been released, including
# cycles retained by signal handlers. Destroying it before widgets can crash Qt.
_qt_app_instance = None


@pytest.fixture(scope="session")
def qt_app():
    global _qt_app_instance
    app = _qt_app_instance = QApplication.instance() or QApplication([])
    yield app
    for widget in app.topLevelWidgets():
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    gc.collect()


@pytest.fixture
def wait_until(qt_app):
    def wait(predicate, timeout=3):
        deadline = time.monotonic() + timeout
        while not predicate():
            qt_app.processEvents()
            if time.monotonic() >= deadline:
                pytest.fail("Timed out waiting for Qt/background operation")
            time.sleep(0.005)
        qt_app.processEvents()

    return wait
