"""RunePilot FastAPI endpoint definitions — health-check, automation control, champion list."""

from __future__ import annotations

from fastapi import FastAPI

from rune_pilot.shared.app_meta import __version__
from rune_pilot.domain.models import AutomationConfig
from rune_pilot.application.automation import (
    RUNNING,
    CURRENT_CONFIG,
    AUTOMATION_THREAD,
    AUTOMATION_LOCK,
    automation_loop,
)
from rune_pilot.application.champion_query import get_champions as _get_champions

import threading


def register_routes(app: FastAPI) -> None:
    """Registers all FastAPI routes on the app."""

    @app.get("/health")
    def health():
        """Simple health-check endpoint."""
        from rune_pilot.application.automation import RUNNING as _running
        return {"status": "ok", "running": _running, "version": __version__}

    @app.get("/champions")
    def champions():
        """Returns the list of owned champions for the UI."""
        return _get_champions()

    @app.post("/start_automation")
    def start_automation(config: AutomationConfig):
        """Starts the automation loop or updates the running configuration."""
        import rune_pilot.application.automation as auto

        with auto.AUTOMATION_LOCK:
            auto.CURRENT_CONFIG = config.model_dump()
            already_running = bool(auto.RUNNING)
            auto.RUNNING = True

            if auto.AUTOMATION_THREAD is None or not auto.AUTOMATION_THREAD.is_alive():
                auto.AUTOMATION_THREAD = threading.Thread(target=auto.automation_loop, daemon=True)
                auto.AUTOMATION_THREAD.start()

        return {"status": "updated" if already_running else "started", "config": auto.CURRENT_CONFIG}

    @app.post("/stop_automation")
    def stop_automation():
        """Stops the automation loop (the thread exits on its next iteration)."""
        import rune_pilot.application.automation as auto

        with auto.AUTOMATION_LOCK:
            auto.RUNNING = False
        return {"status": "stopped"}
