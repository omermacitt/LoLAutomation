"""
Uygulama kimlik/sürüm sabitleri.

Tek bir yerden okunur; hiçbir uygulama koduna bağımlı değildir (kesişen katman).
Sürüm, GitHub Releases üzerindeki en son yayınla (`v0.0.2`) hizalı tutulur.
"""

from __future__ import annotations

import os
import sys

__version__ = "0.0.2"

# Görünen ad ve aktif uygulama kimliği (%APPDATA%\RunePilot dizini için).
APP_DISPLAY_NAME = "RunePilot"
APP_ID = "RunePilot"

# Eski sürümlerde kullanılan uygulama kimliği (%APPDATA%\LoLAutomation).
# Kullanıcı ayarları göçü (migration) için korunur.
LEGACY_APP_ID = "LoLAutomation"

# Otomatik güncelleme için varsayılan GitHub deposu.
# `RUNEPILOT_UPDATE_REPO` ortam değişkeni ile override edilebilir.
UPDATE_REPO_DEFAULT = "omermacitt/LoLAutomation"


def _app_dir() -> str:
    """Uygulamanın çalıştığı dizin (donmuş exe veya kaynak dizini)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


# En eski sürümlerin ayar dosyasını uygulama diziniyle aynı yere yazdığı
# varsayımıyla, son-çare göç kaynağı. Yalnızca varlığı kontrol edilir; yoksa yok sayılır.
LEGACY_CONFIG_FILE = os.path.join(_app_dir(), "user_config.json")
