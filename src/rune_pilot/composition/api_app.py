"""RunePilot FastAPI application factory."""

from fastapi import FastAPI

from src.rune_pilot.composition.endpoints import register_routes


def create_app() -> FastAPI:
    """Creates and configures the FastAPI application."""
    application = FastAPI(title="RunePilot API")
    register_routes(application)
    return application


app = create_app()
