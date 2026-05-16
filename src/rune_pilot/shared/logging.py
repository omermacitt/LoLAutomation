"""
RunePilot loglama yardımcıları.

`run_app.py` içindeki log fonksiyonlarının yeniden kullanılabilir hali.
"""

from __future__ import annotations

import datetime
import os
import traceback

from src.rune_pilot.shared.app_meta import APP_ID


def get_log_path() -> str:
    """Uygulama log dosyası yolunu (`%APPDATA%\\RunePilot\\run_app.log`) döndürür."""
    base_dir = os.getenv("APPDATA") or os.path.expanduser("~")
    return os.path.join(base_dir, APP_ID, "run_app.log")


def log_line(message: str) -> None:
    """Log dosyasına tek satır yazar (hataları sessizce yutar)."""
    try:
        log_path = get_log_path()
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
    except Exception:
        pass


def format_exception(e: Exception) -> str:
    """Exception'ı stacktrace ile string'e çevirir."""
    return "".join(traceback.format_exception(type(e), e, e.__traceback__)).strip()
