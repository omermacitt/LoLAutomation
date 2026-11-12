"""Install/uninstall only on a disposable GitHub Windows runner, never a user's PC."""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from smoke_backend import run


def smoke(installer: Path, legacy: Path | None = None, previous: Path | None = None) -> dict:
    if os.name != "nt" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Installer smoke requires a disposable GitHub Windows runner")
    with tempfile.TemporaryDirectory(prefix="RunePilotInstaller-") as temporary:
        root = Path(temporary)
        install = root / "app"
        profile = Path(os.environ["APPDATA"]) / "RunePilot"
        profile.mkdir(exist_ok=True)
        config = profile / "user_config.json"
        if config.exists():
            raise RuntimeError("Refusing to replace an existing profile")
        original = json.dumps(
            {
                "queue_name": "Ranked Flex",
                "primary_role": "MIDDLE",
                "secondary_role": "BOTTOM",
                "role_champions_ui": {"TOP": [106, 266, None], "MIDDLE": [106, 103, None]},
                "role_bans_ui": {"TOP": 84, "MIDDLE": 238},
                "custom_runes": {
                    "106": {
                        "1": {
                            "name": "Top preset",
                            "primaryStyleId": 8000,
                            "subStyleId": 8300,
                            "selectedPerkIds": [
                                8005,
                                9111,
                                9104,
                                8014,
                                8304,
                                8345,
                                5005,
                                5008,
                                5001,
                            ],
                        }
                    }
                },
                "rune_selection": {"106": 1},
                "role_rune_selection": {"TOP": {"106": 1}, "MIDDLE": {"106": 0}},
                "custom_skins": {"TOP": {"106": 106001}},
                "custom_summoner_spells": {"TOP": {"106": {"spell1Id": 4, "spell2Id": 12}}},
                "preferences": {"unrelated_field": "keep"},
            },
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        config.write_bytes(original)
        legacy_files = []
        if legacy is not None:
            legacy_dir = root / "old-app"
            subprocess.run(
                [
                    str(legacy),
                    "/VERYSILENT",
                    "/SUPPRESSMSGBOXES",
                    "/NORESTART",
                    f"/DIR={legacy_dir}",
                ],
                check=True,
                timeout=120,
            )
            assert (legacy_dir / "RunePilot.exe").is_file()
            legacy_files = [p for p in legacy_dir.rglob("*") if p.is_file()]
            unrelated = legacy_dir / "keep-user-file.txt"
            unrelated.write_text("not an installed program file", encoding="utf-8")
        subprocess.run([str(installer), "/S", f"/D={install}"], check=True, timeout=120)
        if legacy is not None:
            assert all(not path.exists() for path in legacy_files), "Legacy installed files remain"
            assert unrelated.is_file(), "Migration deleted an unrelated user file"
            assert config.read_bytes() == original, "Migration changed game settings"
        backend = install / "runepilot-backend.exe"
        gui = install / "runepilot-desktop.exe"
        uninstaller = install / "uninstall.exe"
        assert backend.is_file() and gui.is_file() and uninstaller.is_file()
        expected_binaries = {
            path.name: hashlib.sha256(path.read_bytes()).digest() for path in (gui, backend)
        }
        result = run(backend)
        # The first beta's real UI/normal close is reviewed separately. Here a
        # parent crash checks that the Windows job cannot orphan its sidecar.
        environment = os.environ.copy()
        environment["RUNEPILOT_PROFILE_DIR"] = str(root / "isolated-profile")
        environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
        for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
            environment.pop(key, None)
        child = subprocess.Popen([str(gui)], cwd=install, env=environment)
        try:
            deadline = time.monotonic() + 25
            owned = []
            while time.monotonic() < deadline:
                assert child.poll() is None, "Native host exited during startup"
                # Fixed executable name and numeric PID; no command lines/tokens.
                query = f"Get-CimInstance Win32_Process -Filter \"Name='runepilot-backend.exe' AND ParentProcessId={child.pid}\" | Select-Object -ExpandProperty ProcessId | ConvertTo-Json"
                output = subprocess.check_output(
                    ["powershell.exe", "-NoProfile", "-Command", query], text=True, timeout=10
                )
                if output.strip():
                    parsed = json.loads(output)
                    owned = parsed if isinstance(parsed, list) else [parsed]
                    break
                time.sleep(0.2)
            assert owned, "Native host did not launch its sidecar"
            child.kill()
            child.wait(timeout=10)
            for pid in owned:
                query = f"Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"
                for _ in range(25):
                    output = subprocess.run(
                        ["powershell.exe", "-NoProfile", "-Command", query],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    ).stdout
                    if not output.strip():
                        break
                    time.sleep(0.2)
                assert not output.strip(), "Sidecar survived native parent crash"
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)
        # _?= keeps NSIS in this process so waiting observes actual uninstall.
        subprocess.run([str(uninstaller), "/S", f"_?={install}"], check=True, timeout=60)
        assert not gui.exists() and not backend.exists()
        assert config.read_bytes() == original, "Uninstall changed the game profile"
        if previous is not None:
            upgrade = root / "native-upgrade"
            subprocess.run([str(previous), "/S", f"/D={upgrade}"], check=True, timeout=120)
            retired = upgrade / "retired" / "owned-old-code.txt"
            assert retired.is_file(), "Previous fixture must install the retired component"
            unrelated = upgrade / "keep-user-file.txt"
            unrelated.write_text("not an installed component", encoding="utf-8")
            subprocess.run(
                [str(installer), "/S", "/UPDATE", f"/D={upgrade}"], check=True, timeout=120
            )
            assert not retired.exists(), "Update left retired code from the previous package"
            assert unrelated.is_file(), "Update removed an unrelated user file"
            for name, digest in expected_binaries.items():
                assert hashlib.sha256((upgrade / name).read_bytes()).digest() == digest
            assert config.read_bytes() == original, "Native update changed game settings"
            subprocess.run(
                [str(upgrade / "uninstall.exe"), "/S", f"_?={upgrade}"], check=True, timeout=60
            )
        return {
            **result,
            "installer": True,
            "uninstall_preserves_profile": True,
            "native_crash_cleanup": True,
            "legacy_replacement": legacy is not None,
            "native_upgrade": previous is not None,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("installer", type=Path)
    parser.add_argument("--legacy", type=Path)
    parser.add_argument("--previous", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            smoke(
                args.installer.resolve(),
                args.legacy.resolve() if args.legacy else None,
                args.previous.resolve() if args.previous else None,
            )
        )
    )
