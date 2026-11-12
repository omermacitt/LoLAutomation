"""Verify a downloaded release's feed references its exact signed Setup asset."""

import json
import sys
from pathlib import Path

from release_updates import manifest


def verify(directory: Path, tag: str, repo: str) -> None:
    actual = json.loads((directory / "latest.json").read_text(encoding="utf-8"))
    expected = manifest(directory, tag.removeprefix("v"), repo)
    for field in ("version", "platforms"):
        if actual.get(field) != expected[field]:
            raise ValueError(f"Update metadata does not match release: {field}")


if __name__ == "__main__":
    verify(Path(sys.argv[1]), sys.argv[2], sys.argv[3])
