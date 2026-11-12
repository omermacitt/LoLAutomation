"""Run the frozen backend outside the checkout with an isolated profile."""

import argparse
import json
import os
import queue
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


def run(executable: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="runepilot-packaged-test-") as directory:
        root = Path(directory)
        target = root / "runepilot-backend.exe"
        shutil.copy2(executable, target)
        profile = root / "profile"
        profile.mkdir()
        (profile / "user_config.json").write_text(
            '{"queue_name":"Ranked Flex","accounts":[]}', encoding="utf-8"
        )
        environment = {
            key: value
            for key, value in os.environ.items()
            if key not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}
        }
        environment["PATH"] = str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32")
        token = secrets.token_hex(32)
        started = time.monotonic()
        child = subprocess.Popen(
            [str(target)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            cwd=root,
            env=environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        errors: list[str] = []
        threading.Thread(target=lambda: errors.append(child.stderr.read()), daemon=True).start()
        messages: queue.Queue = queue.Queue()
        threading.Thread(target=lambda: messages.put(child.stdout.readline()), daemon=True).start()
        try:
            child.stdin.write(json.dumps({"token": token, "profile_dir": str(profile)}) + "\n")
            child.stdin.flush()
            line = messages.get(timeout=60)
            assert token not in line, "Session must not appear in readiness output"
            ready = json.loads(line)
            assert ready["event"] == "ready" and ready["protocol"] == 1
            origin = f"http://127.0.0.1:{ready['port']}"

            def request(path, *, authorized=True, method="GET", data=None, headers=None):
                fields = {"X-RunePilot-Desktop": token} if authorized else {}
                fields.update(headers or {})
                payload = None if data is None else json.dumps(data).encode()
                if payload is not None:
                    fields["Content-Type"] = "application/json"
                req = urllib.request.Request(
                    origin + path, headers=fields, method=method, data=payload
                )
                try:
                    return urllib.request.urlopen(req, timeout=5)
                except urllib.error.HTTPError as error:
                    return error

            assert request("/health", authorized=False).code == 401
            health = json.load(request("/health"))
            assert health["status"] == "ok" and health["running"] is False
            assert health["version"] == ready["version"]
            # No role means no League query and no guessed recommendation, even
            # outside the source checkout and without a bundled rune dataset.
            recommendation = json.load(request("/champions/106/runes/recommended"))
            assert recommendation["source"] == "league"
            assert recommendation["role"] is None
            assert recommendation["unavailableReason"] == "role_required"
            assert recommendation["page"] is None and recommendation["options"] == []
            for retired in ("/accounts", "/login-jobs/active", "/league/launch"):
                assert request(retired).code == 404
            loaded = request("/settings")
            revision = loaded.headers["etag"]
            settings = json.load(loaded)
            assert settings["queue_name"] == "Ranked Flex"
            assert settings["role_rune_selection"] == {}
            settings["role_rune_selection"] = {
                "TOP": {"106": 1},
                "MIDDLE": {"106": 2},
                "JUNGLE": {"106": 0},
            }
            assert (
                request(
                    "/settings", method="PUT", data=settings, headers={"If-Match": revision}
                ).code
                == 200
            )
            assert "accounts" not in json.loads(
                (profile / "user_config.json").read_text(encoding="utf-8")
            )
            assert (
                json.load(request("/settings"))["role_rune_selection"]
                == settings["role_rune_selection"]
            )
            assert json.load(request("/health"))["running"] is False
            # Closing the controlling pipe simulates the native parent's exit.
            child.stdin.close()
            assert child.wait(timeout=20) == 0
            assert not any(token in error for error in errors)
            return {
                "version": ready["version"],
                "protocol": ready["protocol"],
                "source_free": True,
                "isolated_profile": True,
                "parent_eof_shutdown": True,
                "role_rune_round_trip": True,
                "league_recommendation_contract": True,
                "startup_seconds": round(time.monotonic() - started, 2),
            }
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    options = parser.parse_args()
    print(json.dumps(run(options.executable.resolve())))
