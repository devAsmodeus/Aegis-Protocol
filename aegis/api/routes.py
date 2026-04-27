"""HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from aegis.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    """Liveness response payload."""

    status: str
    version: str


@router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """Return service liveness and version. Used by load balancers and CI smoke tests."""
    settings = get_settings()
    return HealthResponse(status="ok", version=settings.app_version)
