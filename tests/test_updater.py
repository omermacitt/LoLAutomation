"""
Güncelleyici (updater) mantığının testleri — sürüm karşılaştırma, asset seçimi ve
GitHub cevabının parse'ı (ağ mock'lanır).
"""

from rune_pilot.application.update_service import UpdateService
from rune_pilot.domain import update as updater
from rune_pilot.infrastructure.github_updates import GithubUpdateSource


def test_parse_version_variants():
    assert updater._parse_version("v0.0.2") == (0, 0, 2)
    assert updater._parse_version("1.2.3") == (1, 2, 3)
    assert updater._parse_version("v2.0.0-beta") == (2, 0, 0)


def test_is_newer():
    assert updater._is_newer("v0.0.3", "0.0.2") is True
    assert updater._is_newer("0.0.2", "0.0.2") is False
    assert updater._is_newer("0.0.1", "0.0.2") is False
    assert updater._is_newer("1.0.0", "0.9.9") is True
    # Farklı uzunluklar: 1.2 vs 1.2.0 eşit.
    assert updater._is_newer("1.2", "1.2.0") is False


def test_prerelease_precedence_and_build_metadata():
    assert updater._is_newer("1.0.0-beta.2", "1.0.0-beta.1")
    assert updater._is_newer("1.0.0-beta.10", "1.0.0-beta.2")
    assert updater._is_newer("1.0.0", "1.0.0-rc.1")
    assert not updater._is_newer("1.0.0-rc.1", "1.0.0")
    assert not updater._is_newer("1.0.0+new-build", "1.0.0+old-build")
    assert not updater._is_newer("1.0.0-beta.1", "1.0.0-beta.2")


def test_pick_asset_prefers_setup_exe():
    assets = [
        {"name": "notes.txt", "browser_download_url": "u1"},
        {"name": "RunePilot.exe", "browser_download_url": "u3"},
        {"name": "RunePilotSetup-0.0.3.exe", "browser_download_url": "u2"},
    ]
    asset = updater._pick_asset(assets)
    assert asset["name"] == "RunePilotSetup-0.0.3.exe"


def test_pick_asset_falls_back_to_first_downloadable():
    assets = [{"name": "data.zip", "browser_download_url": "u1"}]
    assert updater._pick_asset(assets)["browser_download_url"] == "u1"


def test_pick_asset_empty():
    assert updater._pick_asset([]) is None


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    status_code = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_check_for_update_returns_info_when_newer():
    payload = {
        "tag_name": "v0.0.3",
        "name": "RunePilot v0.0.3",
        "body": "Yenilikler",
        "html_url": "https://github.com/x/y/releases/tag/v0.0.3",
        "assets": [{"name": "RunePilotSetup-0.0.3.exe", "browser_download_url": "dl"}],
    }
    source = GithubUpdateSource("x/y", get=lambda *a, **k: _FakeResp(payload))

    info = UpdateService(source, current_version="0.0.2").check()
    assert info is not None
    assert info.latest_version == "0.0.3"
    assert info.asset_download_url == "dl"
    assert info.asset_name == "RunePilotSetup-0.0.3.exe"
    assert info.release_html_url.endswith("v0.0.3")


def test_check_for_update_none_when_not_newer():
    payload = {"tag_name": "v0.0.2", "assets": []}
    source = GithubUpdateSource("x/y", get=lambda *a, **k: _FakeResp(payload))
    assert UpdateService(source, current_version="0.0.2").check() is None
