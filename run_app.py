"""
RunePilot giriş noktası.

FastAPI servisini (arka planda) başlatır ve PyQt masaüstü arayüzünü açar.
PyInstaller ile exe üretmek için `run_app.spec` kullanılır.
"""

import threading
import sys
import os
import datetime
import traceback

# Ensure the current directory is in sys.path so we can import modules
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app_meta import APP_DISPLAY_NAME, APP_ID

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

def start_server() -> None:
    """FastAPI servisini uvicorn ile başlatır (thread içinde çalışır)."""
    try:
        import uvicorn

        log_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "simple": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "simple",
                    "stream": "ext://sys.stderr",
                },
            },
            "loggers": {
                "uvicorn": {"handlers": ["default"], "level": "INFO"},
                "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
                "uvicorn.access": {"handlers": ["default"], "level": "WARNING", "propagate": False},
            },
        }
        from api import app

        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info", log_config=log_config)
    except Exception as e:
        log_line(f"[RUN_APP] Failed to start API: {e}")
        log_line(format_exception(e))

if __name__ == "__main__":
    log_line(f"[RUN_APP] Starting {APP_DISPLAY_NAME}")

    try:
        # Start API in a separate thread
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()

        # Run the GUI in the main thread
        from desktop_app import main as start_gui

        start_gui()
    except Exception as e:
        log_line(f"[RUN_APP] Fatal error: {e}")
        log_line(format_exception(e))
        raise
