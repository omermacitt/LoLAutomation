"""
LCU (League Client Update) API helper.

League of Legends istemcisi, yerel makinede (127.0.0.1) HTTPS üzerinden bir API
yayınlar. Bu API'ye erişim için lockfile içindeki port/şifre bilgisi gerekir.
"""

from __future__ import annotations

from typing import Any

import os

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_LOCKFILE_PATHS: tuple[str, ...] = (
    r"C:\Riot Games\League of Legends\lockfile",
    r"C:\Program Files\Riot Games\League of Legends\lockfile",
    r"C:\Program Files (x86)\Riot Games\League of Legends\lockfile",
)


def find_lockfile_path() -> str:
    """
    Lockfile yolunu bulur.

    Öncelik:
    1) `LOL_LOCKFILE` / `LOL_LOCKFILE_PATH` ortam değişkeni
    2) Yaygın kurulum yolları (`DEFAULT_LOCKFILE_PATHS`)
    """
    env_path = os.getenv("LOL_LOCKFILE") or os.getenv("LOL_LOCKFILE_PATH")
    if env_path:
        env_path = os.path.expandvars(env_path)
        if os.path.exists(env_path):
            return env_path

    for path in DEFAULT_LOCKFILE_PATHS:
        if os.path.exists(path):
            return path

    raise FileNotFoundError(
        "League Client lockfile bulunamadı. League Client'ın açık olduğundan emin olun "
        "ve gerekirse `LOL_LOCKFILE` ortam değişkenini lockfile yoluna ayarlayın."
    )


def get_lcu_credentials(lockfile_path: str | None = None) -> tuple[str, str]:
    """
    Lockfile'dan (port, password) okur.

    Lockfile formatı genelde: `name:pid:port:password:protocol`
    """
    path = lockfile_path or find_lockfile_path()
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        parts = f.read().strip().split(":")

    if len(parts) < 4:
        raise ValueError(f"Beklenmeyen lockfile formatı: {path}")

    port = parts[2].strip()
    password = parts[3].strip()
    if not port or not password:
        raise ValueError(f"Lockfile içinde port/şifre boş: {path}")
    return port, password


def lcu_request(method: str, endpoint: str, json_body: Any | None = None) -> requests.Response:
    """
    LCU API'ye authenticated istek atar.

    `endpoint` değeri `/lol-...` gibi başlamalıdır.
    """
    port, password = get_lcu_credentials()
    url = f"https://127.0.0.1:{port}{endpoint}"
    return requests.request(
        method=str(method).upper(),
        url=url,
        json=json_body,
        auth=("riot", password),
        verify=False,
    )
