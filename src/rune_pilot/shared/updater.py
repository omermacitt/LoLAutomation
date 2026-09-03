"""RunePilot auto-update support — checks GitHub Releases and downloads updates."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import requests


@dataclass
class UpdateInfo:
    """Holds information about an available update."""

    current_version: str = ""
    latest_version: str = ""
    release_notes: str = ""
    release_html_url: str = ""
    asset_download_url: str = ""
    asset_name: str = ""


def check_for_update(
    *,
    current_version: str,
    repo: str,
    token: Optional[str] = None,
    timeout_sec: float = 5.0,
) -> Optional[UpdateInfo]:
    """
    Checks GitHub Releases API for a newer version.

    Returns an `UpdateInfo` if a newer version exists; otherwise `None`.
    """
    if not repo:
        return None

    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        resp = requests.get(url, headers=headers, timeout=timeout_sec)
        if resp.status_code != 200:
            return None

        data = resp.json()
        if not isinstance(data, dict):
            return None

        tag = str(data.get("tag_name") or "").lstrip("vV").strip()
        if not tag:
            return None

        # Simple version comparison
        cur = current_version.lstrip("vV").strip()
        if tag == cur:
            return None

        # Find the installer asset
        asset_url = ""
        asset_name = ""
        assets = data.get("assets") or []
        for a in assets:
            if not isinstance(a, dict):
                continue
            name = str(a.get("name") or "")
            if name.lower().endswith(".exe"):
                asset_url = str(a.get("browser_download_url") or "")
                asset_name = name
                break

        return UpdateInfo(
            current_version=cur,
            latest_version=tag,
            release_notes=str(data.get("body") or ""),
            release_html_url=str(data.get("html_url") or ""),
            asset_download_url=asset_url,
            asset_name=asset_name,
        )
    except Exception:
        return None


def download_asset(
    url: str,
    dest_path: str,
    *,
    token: Optional[str] = None,
    timeout_sec: float = 300.0,
) -> tuple[bool, str]:
    """
    Downloads a file from the given URL.

    Returns: (success, error_message)
    """
    if not url:
        return False, "URL is empty"

    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.get(url, headers=headers, timeout=timeout_sec, stream=True)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"

        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
        return True, ""
    except Exception as e:
        return False, str(e)
