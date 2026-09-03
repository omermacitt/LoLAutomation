"""Development entry point: runs the FastAPI service standalone (no GUI)."""

import os
import sys

# Allow running straight from a source checkout, with no `pip install -e .`
_SRC_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "src")
if os.path.isdir(_SRC_DIR) and _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import uvicorn

from rune_pilot.composition.api_app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
