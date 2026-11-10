"""Public update contracts and pure GitHub release selection."""

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


def select_update(data: dict, current_version: str) -> UpdateInfo | None:
    tag = str(data.get("tag_name") or "").lstrip("vV").strip()
    current = current_version.lstrip("vV").strip()
    if not tag or tag == current:
        return None
    asset_url, asset_name = "", ""
    assets = data.get("assets") or []
    if isinstance(assets, list):
        for asset in assets:
            if isinstance(asset, dict) and str(asset.get("name") or "").lower().endswith(".exe"):
                asset_url = str(asset.get("browser_download_url") or "")
                asset_name = str(asset["name"])
                break
    return UpdateInfo(
        current_version=current, latest_version=tag,
        release_notes=str(data.get("body") or ""),
        release_html_url=str(data.get("html_url") or ""),
        asset_download_url=asset_url, asset_name=asset_name,
    )
