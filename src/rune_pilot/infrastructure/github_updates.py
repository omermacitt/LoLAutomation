"""GitHub update network access and isolated local installer downloads."""

import os
import re
import shutil
import tempfile
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit

import requests

from rune_pilot.domain.update import UpdateInfo


class GithubUpdateSource:
    def __init__(
        self,
        repo: str,
        token: str | None = None,
        *,
        get=requests.get,
        download_root: str | None = None,
    ):
        self._repo = repo.strip()
        self._token = token
        self._get = get
        self._download_root = download_root

    def latest_release(self) -> dict | None:
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", self._repo):
            return None
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            with self._get(
                f"https://api.github.com/repos/{self._repo}/releases/latest",
                headers=headers,
                timeout=4.0,
            ) as response:
                if response.status_code != 200:
                    return None
                data = response.json()
                return data if isinstance(data, dict) else None
        except Exception:
            return None

    def download(self, info: UpdateInfo) -> str:
        name = info.asset_name.strip()
        if (
            not name
            or PureWindowsPath(name).name != name
            or "/" in name
            or "\\" in name
            or ":" in name
            or not name.lower().endswith(".exe")
        ):
            raise ValueError("Invalid installer filename")
        url = urlsplit(info.asset_download_url)
        if (
            url.scheme != "https"
            or url.netloc != "github.com"
            or not url.path.startswith(f"/{self._repo}/releases/download/")
            or url.fragment
        ):
            raise ValueError("Invalid installer URL")
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        directory = tempfile.mkdtemp(prefix="runepilot-update-", dir=self._download_root)
        destination = Path(directory) / name
        try:
            with self._get(
                info.asset_download_url, headers=headers, timeout=300.0, stream=True
            ) as response:
                response.raise_for_status()
                with destination.open("wb") as target:
                    for chunk in response.iter_content(chunk_size=65536):
                        if chunk:
                            target.write(chunk)
            if destination.stat().st_size == 0:
                raise ValueError("Empty installer")
            return os.fspath(destination)
        except Exception:
            # Only the newly created, isolated directory is removed.
            shutil.rmtree(directory)
            raise
