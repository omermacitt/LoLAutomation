"""
LCU (League Client Update) API helper.

The League of Legends client exposes a local HTTPS API on 127.0.0.1.
Access requires the port and password from the lockfile.
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
    Locates the League Client lockfile.

    Priority:
    1) `LOL_LOCKFILE` / `LOL_LOCKFILE_PATH` environment variable
    2) Common installation paths (`DEFAULT_LOCKFILE_PATHS`)
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
        "League Client lockfile not found. Make sure League Client is running "
        "and set the `LOL_LOCKFILE` environment variable if it is installed in a non-standard path."
    )


def get_lcu_credentials(lockfile_path: str | None = None) -> tuple[str, str]:
    """
    Reads (port, password) from the lockfile.

    Lockfile format: `name:pid:port:password:protocol`
    """
    path = lockfile_path or find_lockfile_path()
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        parts = f.read().strip().split(":")

    if len(parts) < 4:
        raise ValueError(f"Unexpected lockfile format: {path}")

    port = parts[2].strip()
    password = parts[3].strip()
    if not port or not password:
        raise ValueError(f"Port or password is empty in lockfile: {path}")
    return port, password


def lcu_request(method: str, endpoint: str, json_body: Any | None = None) -> requests.Response:
    """
    Sends an authenticated request to the LCU API.

    `endpoint` must start with `/lol-...`.
    """
    port, password = get_lcu_credentials()
    url = f"https://127.0.0.1:{port}{endpoint}"
    return requests.request(
        method=str(method).upper(),
        url=url,
        json=json_body,
        auth=("riot", password),
        verify=False,
        timeout=2.0,
    )
