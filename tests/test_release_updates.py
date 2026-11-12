"""Release metadata never mixes versions, platforms or a different signature."""

import base64
import importlib.util
import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
spec = importlib.util.spec_from_file_location("release_updates", TOOLS / "release_updates.py")
release_updates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_updates)
sys.modules["release_updates"] = release_updates
spec = importlib.util.spec_from_file_location("verify_update_feed", TOOLS / "verify_update_feed.py")
verify_feed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify_feed)


def test_complete_setup_signature_and_feed_refer_to_the_same_version(tmp_path):
    setup = tmp_path / "RunePilotSetup-1.0.0-x64.exe"
    setup.write_bytes(b"synthetic-complete-setup")
    signature = base64.b64encode(b"untrusted comment: fixture\nsignature").decode()
    setup.with_suffix(".exe.sig").write_text(signature, encoding="utf-8")
    data = release_updates.manifest(tmp_path, "1.0.0", "test/app", "Notes")
    assert data["platforms"]["windows-x86_64"] == {
        "url": "https://github.com/test/app/releases/download/v1.0.0/RunePilotSetup-1.0.0-x64.exe",
        "signature": signature,
    }
    feed = tmp_path / "latest.json"
    feed.write_text(json.dumps(data), encoding="utf-8")
    verify_feed.verify(tmp_path, "v1.0.0", "test/app")
    data["version"] = "2.0.0"
    feed.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        verify_feed.verify(tmp_path, "v1.0.0", "test/app")


def test_missing_package_and_invalid_signature_cannot_create_a_feed(tmp_path):
    with pytest.raises(ValueError, match="missing"):
        release_updates.manifest(tmp_path, "1.0.0-beta.2", "test/app")
    (tmp_path / "RunePilotSetup-1.0.0-beta.2-x64.exe").write_bytes(b"fixture")
    (tmp_path / "RunePilotSetup-1.0.0-beta.2-x64.exe.sig").write_text("invalid", encoding="utf-8")
    with pytest.raises(ValueError):
        release_updates.manifest(tmp_path, "1.0.0-beta.2", "test/app")
