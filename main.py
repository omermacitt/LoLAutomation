"""Geliştirme amaçlı: FastAPI servisini tek başına çalıştırır (GUI olmadan)."""

import uvicorn

from src.rune_pilot.composition.api_app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
