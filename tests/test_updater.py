"""
Güncelleyici (updater) mantığının testleri — sürüm karşılaştırma, asset seçimi ve
GitHub cevabının parse'ı (ağ mock'lanır).
"""

import updater


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


def test_pick_asset_prefers_setup_exe():
    assets = [
        {"name": "notes.txt", "browser_download_url": "u1"},
        {"name": "RunePilotSetup-0.0.3.exe", "browser_download_url": "u2"},
        {"name": "RunePilot.exe", "browser_download_url": "u3"},
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

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_check_for_update_returns_info_when_newer(monkeypatch):
    payload = {
        "tag_name": "v0.0.3",
        "name": "RunePilot v0.0.3",
        "body": "Yenilikler",
        "html_url": "https://github.com/x/y/releases/tag/v0.0.3",
        "assets": [{"name": "RunePilotSetup-0.0.3.exe", "browser_download_url": "dl"}],
    }
    monkeypatch.setattr(updater.requests, "get", lambda *a, **k: _FakeResp(payload))

    info = updater.check_for_update(current_version="0.0.2", repo="x/y")
    assert info is not None
    assert info.latest_version == "v0.0.3"
    assert info.asset_download_url == "dl"
    assert info.asset_name == "RunePilotSetup-0.0.3.exe"
    assert info.release_html_url.endswith("v0.0.3")


def test_check_for_update_none_when_not_newer(monkeypatch):
    payload = {"tag_name": "v0.0.2", "assets": []}
    monkeypatch.setattr(updater.requests, "get", lambda *a, **k: _FakeResp(payload))
    assert updater.check_for_update(current_version="0.0.2", repo="x/y") is None
