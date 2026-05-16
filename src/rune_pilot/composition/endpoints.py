"""
RunePilot FastAPI endpoint tanımları.

Health-check, otomasyon başlatma/durdurma ve şampiyon listesi endpoint'leri.
"""

from __future__ import annotations

from fastapi import FastAPI

from src.rune_pilot.shared.app_meta import __version__
from src.rune_pilot.domain.models import AutomationConfig
from src.rune_pilot.application.automation import (
    RUNNING,
    CURRENT_CONFIG,
    AUTOMATION_THREAD,
    AUTOMATION_LOCK,
    automation_loop,
)
from src.rune_pilot.application.champion_query import get_champions as _get_champions

import threading


def register_routes(app: FastAPI) -> None:
    """Tüm FastAPI route'larını app'e kaydeder."""

    @app.get("/health")
    def health():
        """Basit health-check endpoint'i."""
        from src.rune_pilot.application.automation import RUNNING as _running
        return {"status": "ok", "running": _running, "version": __version__}

    @app.get("/champions")
    def champions():
        """UI için sahip olunan şampiyon listesini döndürür."""
        return _get_champions()

    @app.post("/start_automation")
    def start_automation(config: AutomationConfig):
        """Otomasyonu başlatır veya çalışan konfigürasyonu günceller."""
        import src.rune_pilot.application.automation as auto

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
        """Otomasyonu durdurur (thread bir sonraki turda döngüden çıkar)."""
        import src.rune_pilot.application.automation as auto

        with auto.AUTOMATION_LOCK:
            auto.RUNNING = False
        return {"status": "stopped"}
