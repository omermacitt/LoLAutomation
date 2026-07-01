"""
Paketlenmiş kaynak dosyalarına (runes.json, assets/...) güvenli mutlak yol üretir.

Hem geliştirme (kaynaktan çalıştırma) hem de PyInstaller (donmuş exe) için çalışır.
Daha önce `api.py` ve `desktop_app.py`'de birebir kopyalanan `resource_path`'in tek kaynağıdır.
"""

from __future__ import annotations

import os
import sys


def _project_root() -> str:
    """
    Kaynakların bulunduğu proje kökü.

    Bu dosya `runepilot/infrastructure/` altında olduğundan proje kökü iki üst dizindir.
    Kaynaklar (runes.json, assets/) kökte durur, bu yüzden onları buradan çözeriz.
    """
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def resource_path(relative_path: str) -> str:
    """
    Bir kaynağın mutlak yolunu döndürür (dev + PyInstaller uyumlu).

    Donmuş exe'de PyInstaller kaynakları `sys._MEIPASS` altına açar; aksi halde
    proje kökünü baz alırız (CWD'ye bağımlı kalmamak için).
    """
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = _project_root()
    return os.path.join(base_path, relative_path)
