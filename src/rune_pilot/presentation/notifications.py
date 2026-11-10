"""
Windows toast notifications, with the library treated as optional.

`win10toast` is unmaintained and imports `pkg_resources`, which setuptools removed in
version 81. On an up-to-date environment the import therefore raises, and because the
old code imported it at module scope that took the whole window down with it. A missed
toast is not worth failing to start over, so every call here degrades to a no-op and
says why once.
"""

from __future__ import annotations

DEFAULT_DURATION_SEC = 5


class DesktopNotifier:
    """Shows toasts when the platform supports them, and nothing when it does not."""

    def __init__(self) -> None:
        self._toaster = None
        self._unavailable_reason = ""
        try:
            from win10toast import ToastNotifier
        except Exception as e:  # ImportError today, but the cause is not worth narrowing
            self._unavailable_reason = str(e)
            print(f"[NOTIFY] Toast notifications disabled: {e}")
            return

        try:
            self._toaster = ToastNotifier()
        except Exception as e:
            self._unavailable_reason = str(e)
            print(f"[NOTIFY] Toast notifications disabled: {e}")

    @property
    def available(self) -> bool:
        return self._toaster is not None

    def show(self, title: str, message: str, duration: int = DEFAULT_DURATION_SEC) -> None:
        """Shows a toast. Never raises — the caller is mid-automation."""
        if self._toaster is None:
            return
        try:
            self._toaster.show_toast(title, message, duration=duration, threaded=True)
        except Exception as e:
            print(f"[NOTIFY] Could not show toast: {e}")
