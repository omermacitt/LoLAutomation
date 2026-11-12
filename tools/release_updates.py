"""Create a Tauri manifest for the exact versioned, signed complete Setup."""

import argparse
import base64
import json
import re
from datetime import UTC, datetime
from pathlib import Path


def manifest(directory: Path, version: str, repo: str, notes: str = "") -> dict:
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise ValueError("Invalid GitHub repository")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?", version):
        raise ValueError("Invalid release version")
    name = f"RunePilotSetup-{version}-x64.exe"
    setup = directory / name
    if not setup.is_file() or setup.stat().st_size == 0:
        raise ValueError("Complete Setup is missing")
    signature = (directory / f"{name}.sig").read_text(encoding="utf-8").strip()
    decoded = base64.b64decode(signature, validate=True)
    if not decoded.startswith(b"untrusted comment:"):
        raise ValueError("Invalid Tauri update signature")
    return {
        "version": version,
        "notes": notes,
        "pub_date": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "platforms": {
            "windows-x86_64": {
                "signature": signature,
                "url": f"https://github.com/{repo}/releases/download/v{version}/{name}",
            }
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--repo", default="omermacitt/LoLAutomation")
    parser.add_argument("--notes-file", type=Path)
    args = parser.parse_args()
    notes = args.notes_file.read_text(encoding="utf-8") if args.notes_file else ""
    data = manifest(args.directory, args.version, args.repo, notes)
    (args.directory / "latest.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
