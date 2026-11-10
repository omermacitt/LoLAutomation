"""No GitHub calls: stub HTTP and inspect isolated/partial installer writes."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from rune_pilot.domain.update import UpdateInfo
from rune_pilot.infrastructure.github_updates import GithubUpdateSource


def response(status=200):
    result = Mock(status_code=status)
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    return result


def info(name="Setup.exe", url="https://github.com/test/app/releases/download/v2/Setup.exe"):
    return UpdateInfo(asset_name=name, asset_download_url=url)


def test_release_network_settings_and_token_are_backend_only():
    result = response()
    result.json.return_value = {"tag_name": "v2"}
    get = Mock(return_value=result)
    source = GithubUpdateSource("test/app", "secret", get=get)
    assert source.latest_release() == {"tag_name": "v2"}
    get.assert_called_once_with("https://api.github.com/repos/test/app/releases/latest",
                               headers={"Accept": "application/vnd.github+json", "Authorization": "Bearer secret"}, timeout=4.0)
    result.status_code = 403
    assert source.latest_release() is None
    get.side_effect = OSError("offline")
    assert source.latest_release() is None


def test_download_uses_unique_directories_and_closes_response(tmp_path):
    result = response()
    result.iter_content.return_value = [b"MZ", b"", b"installer"]
    get = Mock(return_value=result)
    source = GithubUpdateSource("test/app", get=get, download_root=str(tmp_path))
    first = Path(source.download(info()))
    second = Path(source.download(info()))
    assert first != second
    assert first.parent.parent == tmp_path
    assert first.read_bytes() == second.read_bytes() == b"MZinstaller"
    assert get.call_args.kwargs == {"headers": {}, "timeout": 300.0, "stream": True}
    assert result.__exit__.call_count == 2


def test_partial_or_empty_download_is_removed_and_never_reported_as_installer(tmp_path):
    def chunks(**kwargs):
        yield b"partial"
        raise OSError("disconnected")
    result = response()
    result.iter_content.side_effect = chunks
    source = GithubUpdateSource("test/app", get=Mock(return_value=result), download_root=str(tmp_path))
    with pytest.raises(OSError):
        source.download(info())
    assert list(tmp_path.iterdir()) == []
    result.iter_content.side_effect = None
    result.iter_content.return_value = []
    with pytest.raises(ValueError, match="Empty"):
        source.download(info())
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("name,url", [
    ("../Setup.exe", "https://github.com/test/app/releases/download/v2/Setup.exe"),
    ("C:\\Setup.exe", "https://github.com/test/app/releases/download/v2/Setup.exe"),
    ("Setup.exe:other.exe", "https://github.com/test/app/releases/download/v2/Setup.exe"),
    ("Setup.exe", "http://github.com/test/app/releases/download/v2/Setup.exe"),
    ("Setup.exe", "https://arbitrary.test/Setup.exe"),
    ("Setup.exe", "https://github.com/other/app/releases/download/v2/Setup.exe"),
])
def test_download_rejects_paths_and_assets_outside_configured_repo(tmp_path, name, url):
    get = Mock()
    with pytest.raises(ValueError):
        GithubUpdateSource("test/app", get=get, download_root=str(tmp_path)).download(info(name, url))
    get.assert_not_called()
    assert list(tmp_path.iterdir()) == []
