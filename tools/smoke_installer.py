"""Install/uninstall only on a disposable GitHub Windows runner, never a user's PC."""

import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from smoke_backend import run


def smoke(installer: Path) -> dict:
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
        original = b'{"queue_name":"Ranked Flex"}'
        config.write_bytes(original)
        subprocess.run([str(installer), "/S", f"/D={install}"], check=True, timeout=120)
        backend = install / "runepilot-backend.exe"
        gui = install / "runepilot-desktop.exe"
        uninstaller = install / "uninstall.exe"
        assert backend.is_file() and gui.is_file() and uninstaller.is_file()
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
        return {
            **result,
            "installer": True,
            "uninstall_preserves_profile": True,
            "native_crash_cleanup": True,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("installer", type=Path)
    args = parser.parse_args()
    print(json.dumps(smoke(args.installer.resolve())))
