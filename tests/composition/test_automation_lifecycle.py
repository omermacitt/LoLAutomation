"""HTTP settings never expose progress and API shutdown joins the worker."""

import threading

import pytest
from fastapi.testclient import TestClient

from rune_pilot.application.automation_service import AutomationService
from rune_pilot.composition.api_app import create_app


def test_selection_notice_is_transient_and_hidden_after_stop():
    ready = threading.Event()

    def loop(should_run, snapshot, wait):
        ready.set()
        wait(100)

    service = AutomationService(loop)
    app = create_app(automation_service=service)
    with TestClient(app) as client:
        client.post("/start_automation", json={})
        assert ready.wait(2)
        app.state.selection_feedback.publish((1, 0, 10), "no_preference", "JUNGLE")
        app.state.selection_feedback.publish((1, 0, 10), "no_preference", "JUNGLE")
        notice = client.get("/health").json()["selection"]
        assert notice == {"id": 1, "code": "no_preference", "role": "JUNGLE", "champion_id": None}
        assert "selection" not in service.config
        assert "selection" not in client.get("/settings").json()
        client.post("/stop_automation")
        assert client.get("/health").json()["selection"] is None


def test_api_shutdown_cancels_worker_and_start_returns_only_settings():
    started, finished = threading.Event(), threading.Event()

    def loop(should_run, get_snapshot, wait):
        # Editing the worker copy must not affect subsequent API responses.
        get_snapshot().config["runes_applied"] = True
        started.set()
        wait(100)
        assert not should_run()
        finished.set()

    service = AutomationService(loop)
    with TestClient(create_app(automation_service=service)) as client:
        response = client.post("/start_automation", json={"queue_id": 420, "runes_applied": True})
        assert response.status_code == 200
        assert started.wait(2)
        assert "runes_applied" not in response.json()["config"]
        assert "skin_applied_key" not in service.config
        assert client.get("/health").json()["running"] is True
    assert finished.is_set()
    assert not service.is_running
    with pytest.raises(RuntimeError, match="shutting down"):
        service.start({})


def test_update_running_cannot_start_or_revive_a_stopped_worker():
    started = threading.Event()
    calls = []

    def loop(should_run, get_snapshot, wait):
        calls.append(True)
        started.set()
        wait(100)

    service = AutomationService(loop)
    with TestClient(create_app(automation_service=service)) as client:
        assert client.put("/automation/config", json={"queue_id": 440}).status_code == 409
        assert not calls
        assert client.post("/start_automation", json={"queue_id": 420}).status_code == 200
        assert started.wait(2)
        assert client.put("/automation/config", json={"queue_id": 440}).status_code == 200
        assert service.config["queue_id"] == 440
        assert client.post("/stop_automation").status_code == 200
        assert client.put("/automation/config", json={"queue_id": 400}).status_code == 409
        assert not service.is_running
    assert len(calls) == 1


@pytest.mark.parametrize(
    "method,path", [("POST", "/start_automation"), ("PUT", "/automation/config")]
)
def test_duplicate_role_choices_cannot_enter_automation(method, path):
    service = AutomationService(lambda *args: None)
    with TestClient(create_app(automation_service=service)) as client:
        response = client.request(method, path, json={"role_champions": {"TOP": [266, 266]}})
        assert response.status_code == 422
        assert not service.is_running
        assert service.config == {}
