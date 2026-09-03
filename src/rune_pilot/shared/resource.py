"""PyInstaller-compatible resource path resolver. Works in both dev and bundled modes."""

from __future__ import annotations

import os
import sys


def resource_path(relative_path: str) -> str:
    """Returns an absolute path to a resource, compatible with PyInstaller bundles."""
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        # Use the project root (two levels up from this file: shared/ -> rune_pilot/ -> src/ -> project root)
        base_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir)
        )
    return os.path.join(base_path, relative_path)
