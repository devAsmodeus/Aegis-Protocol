"""Shared FastAPI dependencies (registries, auth, sessions).

Centralizes the keeper registry singleton and the auth helpers so the
``/v1/keeper`` and ``/v1/admin`` routers don't each spin up their own.
Tests override :func:`get_keeper_registry` and the session dependency
via ``app.dependency_overrides``.
"""

from __future__ import annotations

import hmac
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.config import Settings, get_settings
from aegis.keeper import (
    HealthcheckUpstreamsTask,
    KeeperRegistry,
    RefreshDocumentsTask,
    RotateAgentSessionsTask,
)


@lru_cache(maxsize=1)
def _build_default_registry() -> KeeperRegistry:
    """Build the process-wide default registry.

    The default registry holds stub-friendly task instances so the
    server boots without docker. Production wiring (real DB sessions,
    real upstream probes) plugs in via :func:`get_keeper_registry`
    overrides during deployment, not here.
    """
    settings = get_settings()
    registry = KeeperRegistry()
    registry.register(RefreshDocumentsTask())
    registry.register(RotateAgentSessionsTask())
    registry.register(HealthcheckUpstreamsTask(settings=settings))
    return registry


def get_keeper_registry() -> KeeperRegistry:
    """FastAPI dependency: returns the process-wide keeper registry."""
    return _build_default_registry()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields an :class:`AsyncSession`.

    Wraps :func:`aegis.db.session.get_session` so admin routes don't
    have to import the DB module directly. Tests override this with a
    fake session.
    """
    from aegis.db.session import get_session  # local import: keeps app boot lean

    async for session in get_session():
        yield session


def _constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


SettingsDep = Annotated[Settings, Depends(get_settings)]
AuthHeaderDep = Annotated[str | None, Header(alias="Authorization")]
KeeperSigDep = Annotated[str | None, Header(alias="X-Aegis-Keeper-Signature")]


def require_admin_bearer(
    settings: SettingsDep,
    authorization: AuthHeaderDep = None,
) -> None:
    """Reject the request unless the bearer token matches.

    A missing or unconfigured :attr:`Settings.admin_api_token` is a
    misconfiguration, not an open door — we 503 in that case so the
    operator notices.
    """
    if not settings.admin_api_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin_api_token is not configured",
        )
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
        )
    presented = authorization.removeprefix("Bearer ").strip()
    if not _constant_time_eq(presented, settings.admin_api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid bearer token",
        )


async def verify_keeper_signature(
    request: Request,
    settings: SettingsDep,
    x_aegis_keeper_signature: KeeperSigDep = None,
) -> bytes:
    """Verify the HMAC-SHA256 signature on the raw request body.

    On success, returns the raw body so the route handler can re-read
    it without re-buffering. Failure modes:

    * 503 if ``keeper_signing_secret`` is not configured.
    * 401 if the header is missing or the signature does not match.
    """
    import hashlib

    if not settings.keeper_signing_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="keeper_signing_secret is not configured",
        )
    if not x_aegis_keeper_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing X-Aegis-Keeper-Signature",
        )
    body = await request.body()
    expected = hmac.new(
        settings.keeper_signing_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not _constant_time_eq(x_aegis_keeper_signature, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid signature",
        )
    return body


DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
KeeperRegistryDep = Annotated["KeeperRegistry", Depends(get_keeper_registry)]


__all__ = [
    "AuthHeaderDep",
    "DbSessionDep",
    "KeeperRegistryDep",
    "KeeperSigDep",
    "SettingsDep",
    "get_db_session",
    "get_keeper_registry",
    "require_admin_bearer",
    "verify_keeper_signature",
]
