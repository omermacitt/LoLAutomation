"""Synchronize desktop manifests from the Python version; never silently bump it."""

import argparse
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def version() -> str:
    tree = ast.parse((ROOT / "src/rune_pilot/shared/app_meta.py").read_text(encoding="utf-8"))
    value = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        )
    )
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?", value):
        raise ValueError("Use MAJOR.MINOR.PATCH or MAJOR.MINOR.PATCH-beta.N")
    return value


def manifests(value: str) -> dict[Path, str]:
    result = {}
    for name in (
        "frontend/package.json",
        "frontend/package-lock.json",
        "frontend/src-tauri/tauri.conf.json",
    ):
        path = ROOT / name
        data = json.loads(path.read_text(encoding="utf-8"))
        data["version"] = value
        if "packages" in data:
            data["packages"][""]["version"] = value
        result[path] = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    cargo = ROOT / "frontend/src-tauri/Cargo.toml"
    result[cargo] = re.sub(
        r'(?m)^version = "[^"]+"',
        f'version = "{value}"',
        cargo.read_text(encoding="utf-8"),
        count=1,
    )
    lock = ROOT / "frontend/src-tauri/Cargo.lock"
    result[lock] = re.sub(
        r'(name = "runepilot-desktop"\nversion = ")[^"]+',
        rf"\g<1>{value}",
        lock.read_text(encoding="utf-8"),
        count=1,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--tag", help="Expected release tag, e.g. v1.0.0-beta.1")
    parser.add_argument("--print", action="store_true", dest="print_only")
    args = parser.parse_args()
    value = version()
    if args.print_only:
        print(value)
        return
    if args.tag and args.tag != f"v{value}":
        parser.error(f"Tag must be v{value}")
    stale = []
    for path, expected in manifests(value).items():
        if path.read_text(encoding="utf-8") != expected:
            if args.sync:
                path.write_text(expected, encoding="utf-8", newline="\n")
            else:
                stale.append(str(path.relative_to(ROOT)))
    if stale:
        parser.error("Run python tools/release_version.py --sync: " + ", ".join(stale))
    print(f"Desktop manifests match {value}")


if __name__ == "__main__":
    main()
