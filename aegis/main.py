"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI

from aegis.api.admin import router as admin_router
from aegis.api.keeper import router as keeper_router
from aegis.api.routes import router as api_router
from aegis.config import get_settings


def create_app() -> FastAPI:
    """Build and return the configured FastAPI app."""
    settings = get_settings()
    app = FastAPI(
        title="Aegis Protocol",
        description="Trustworthy AI support agent for Web3.",
        version=settings.app_version,
    )
    app.include_router(api_router)
    app.include_router(keeper_router)
    app.include_router(admin_router)
    return app


app = create_app()
