"""
RunePilot entry point.

Starts the FastAPI service in a background thread and opens the PyQt desktop UI.
Use `run_app.spec` to build an EXE with PyInstaller.
"""

import threading
import sys
import os
import datetime
import traceback

# Allow running straight from a source checkout, with no `pip install -e .`
_SRC_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "src")
if os.path.isdir(_SRC_DIR) and _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from rune_pilot.shared.app_meta import APP_DISPLAY_NAME, APP_ID

def get_log_path() -> str:
    """Returns the application log file path (`%APPDATA%\\RunePilot\\run_app.log`)."""
    base_dir = os.getenv("APPDATA") or os.path.expanduser("~")
    return os.path.join(base_dir, APP_ID, "run_app.log")

def log_line(message: str) -> None:
    """Appends a single timestamped line to the log file (silently ignores errors)."""
    try:
        log_path = get_log_path()
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
    except Exception:
        pass

def format_exception(e: Exception) -> str:
    """Formats an exception with its full traceback as a string."""
    return "".join(traceback.format_exception(type(e), e, e.__traceback__)).strip()

def start_server(stop_signal: threading.Event | None = None) -> None:
    """Starts the FastAPI service via uvicorn (runs inside a background thread)."""
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
                "rune_file": {
                    "class": "logging.FileHandler",
                    "filename": get_log_path(), "encoding": "utf-8",
                    "formatter": "simple",
                },
            },
            "loggers": {
                "uvicorn": {"handlers": ["default"], "level": "INFO"},
                "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
                "uvicorn.access": {"handlers": ["default"], "level": "WARNING", "propagate": False},
                "rune_pilot": {"handlers": ["rune_file"], "level": "INFO", "propagate": False},
            },
        }
        from rune_pilot.composition.api_app import create_app
        app = create_app()

        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=8000, log_level="info", log_config=log_config,
        ))
        if stop_signal is not None:
            def wait_for_close() -> None:
                stop_signal.wait()
                server.should_exit = True
            threading.Thread(target=wait_for_close, daemon=True).start()
        server.run()
    except Exception as e:
        log_line(f"[RUN_APP] Failed to start API: {e}")
        log_line(format_exception(e))

if __name__ == "__main__":
    log_line(f"[RUN_APP] Starting {APP_DISPLAY_NAME}")

    server_stop = threading.Event()
    server_thread = None
    try:
        # Start API in a separate thread
        server_thread = threading.Thread(target=start_server, args=(server_stop,), daemon=True)
        server_thread.start()

        # Run the GUI in the main thread
        from rune_pilot.presentation.main_window import main as start_gui

        start_gui()
    except Exception as e:
        log_line(f"[RUN_APP] Fatal error: {e}")
        log_line(format_exception(e))
        raise
    finally:
        server_stop.set()
        if server_thread is not None:
            server_thread.join(timeout=15.0)
            if server_thread.is_alive():
                log_line("[RUN_APP] Backend did not finish shutdown within 15 seconds")
