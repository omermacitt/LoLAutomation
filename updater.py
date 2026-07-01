"""
GitHub Releases tabanlı otomatik güncelleme yardımcıları.

`desktop_app.py` bunları açılışta kullanır:
- `check_for_update(...)` yeni sürüm var mı diye bakar (varsa `UpdateInfo`, yoksa `None`).
- `download_asset(...)` release asset'ini (installer) indirir.

Ağ/IO burada izole edilir (infrastructure katmanı). Hatalar `check_for_update` içinde
exception olarak yükselir (çağıran taraf sessizce yutar), indirmede `(ok, err)` döner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests

GITHUB_API = "https://api.github.com"


@dataclass
class UpdateInfo:
    """Yeni sürüm bilgisi (GUI'ye taşınan sonuç modeli)."""

    current_version: str
    latest_version: str
    release_notes: str | None
    asset_download_url: str | None
    asset_name: str | None
    release_html_url: str | None


def _parse_version(value: str) -> tuple[int, ...]:
    """`v1.2.3` / `1.2.3` gibi bir sürümü karşılaştırılabilir sayı demetine çevirir."""
    s = (value or "").strip().lstrip("vV")
    # Prerelease/build eklerini (ör. `-beta`, `+build`) at.
    s = re.split(r"[-+]", s, maxsplit=1)[0]
    parts: list[int] = []
    for chunk in s.split("."):
        m = re.match(r"\d+", chunk.strip())
        parts.append(int(m.group(0)) if m else 0)
    return tuple(parts) or (0,)


def _is_newer(latest: str, current: str) -> bool:
    """`latest` sürümü `current`'tan yeni mi?"""
    lt = _parse_version(latest)
    cu = _parse_version(current)
    # Uzunlukları eşitle (1.2 vs 1.2.0).
    length = max(len(lt), len(cu))
    lt += (0,) * (length - len(lt))
    cu += (0,) * (length - len(cu))
    return lt > cu


def _auth_headers(token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _pick_asset(assets: list[dict]) -> dict | None:
    """
    İndirilecek installer asset'ini seçer.

    Öncelik: `.exe` (Setup/installer) > ilk uygun asset.
    """
    if not isinstance(assets, list):
        return None

    exe_assets = [
        a
        for a in assets
        if isinstance(a, dict) and str(a.get("name") or "").lower().endswith(".exe")
    ]
    if exe_assets:
        # "setup"/"installer" adı geçen exe'yi tercih et.
        for a in exe_assets:
            name = str(a.get("name") or "").lower()
            if "setup" in name or "installer" in name:
                return a
        return exe_assets[0]

    for a in assets:
        if isinstance(a, dict) and a.get("browser_download_url"):
            return a
    return None


def check_for_update(
    *,
    current_version: str,
    repo: str,
    token: str | None = None,
    timeout_sec: float = 4.0,
) -> UpdateInfo | None:
    """
    `repo` (`owner/name`) için en son release'e bakar.

    Yeni sürüm varsa `UpdateInfo`, yoksa `None` döner. Ağ/parse hataları exception
    olarak yükselir (çağıran taraf yutar).
    """
    url = f"{GITHUB_API}/repos/{repo}/releases/latest"
    res = requests.get(url, headers=_auth_headers(token), timeout=timeout_sec)
    res.raise_for_status()
    data = res.json()
    if not isinstance(data, dict):
        return None

    latest_tag = str(data.get("tag_name") or data.get("name") or "").strip()
    if not latest_tag:
        return None

    if not _is_newer(latest_tag, current_version):
        return None

    asset = _pick_asset(data.get("assets") or [])
    return UpdateInfo(
        current_version=current_version,
        latest_version=latest_tag,
        release_notes=(data.get("body") or None),
        asset_download_url=(asset.get("browser_download_url") if asset else None),
        asset_name=(asset.get("name") if asset else None),
        release_html_url=(data.get("html_url") or None),
    )


def download_asset(
    url: str,
    dest_path: str,
    *,
    token: str | None = None,
    timeout_sec: float = 300.0,
) -> tuple[bool, str | None]:
    """
    Verilen asset URL'sini `dest_path`'e indirir.

    Dönüş: `(ok, err)` — başarılıysa `(True, None)`, değilse `(False, hata_mesajı)`.
    """
    try:
        with requests.get(
            url, headers=_auth_headers(token), stream=True, timeout=timeout_sec
        ) as res:
            res.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        f.write(chunk)
        return True, None
    except Exception as e:  # noqa: BLE001 - hata mesajını çağırana taşıyoruz
        return False, str(e)
