"""Public update contracts and pure GitHub release selection."""

import re

from pydantic import BaseModel, Field


class UpdateInfo(BaseModel):
    update_id: str = ""
    current_version: str = ""
    latest_version: str = ""
    release_notes: str = ""
    release_html_url: str = ""
    asset_download_url: str = ""
    asset_name: str = ""


class UpdateCheck(BaseModel):
    update: UpdateInfo | None = None


class UpdateDownload(BaseModel):
    # The desktop and backend run on the same Windows machine.
    installer_path: str = Field(min_length=1)


def _parse_version(value: str) -> tuple[int, ...]:
    version = re.split(r"[-+]", (value or "").strip().lstrip("vV"), maxsplit=1)[0]
    parts = []
    for chunk in version.split("."):
        match = re.match(r"\d+", chunk.strip())
        parts.append(int(match.group(0)) if match else 0)
    return tuple(parts) or (0,)


def _is_newer(latest: str, current: str) -> bool:
    latest_parts, current_parts = _parse_version(latest), _parse_version(current)
    length = max(len(latest_parts), len(current_parts))
    return latest_parts + (0,) * (length - len(latest_parts)) > current_parts + (0,) * (
        length - len(current_parts)
    )


def _pick_asset(assets: list[dict]) -> dict | None:
    if not isinstance(assets, list):
        return None
    executables = [
        item
        for item in assets
        if isinstance(item, dict) and str(item.get("name") or "").lower().endswith(".exe")
    ]
    for item in executables:
        name = str(item["name"]).lower()
        if "setup" in name or "installer" in name:
            return item
    if executables:
        return executables[0]
    return next(
        (item for item in assets if isinstance(item, dict) and item.get("browser_download_url")),
        None,
    )


def select_update(data: dict, current_version: str) -> UpdateInfo | None:
    tag = str(data.get("tag_name") or "").lstrip("vV").strip()
    current = current_version.lstrip("vV").strip()
    if not tag or not _is_newer(tag, current):
        return None
    asset_url, asset_name = "", ""
    asset = _pick_asset(data.get("assets") or [])
    if asset and str(asset.get("name") or "").lower().endswith(".exe"):
        asset_url = str(asset.get("browser_download_url") or "")
        asset_name = str(asset["name"])
    return UpdateInfo(
        current_version=current,
        latest_version=tag,
        release_notes=str(data.get("body") or ""),
        release_html_url=str(data.get("html_url") or ""),
        asset_download_url=asset_url,
        asset_name=asset_name,
    )
