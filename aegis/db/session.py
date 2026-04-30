"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from aegis.config import get_settings


def make_engine(database_url: str) -> AsyncEngine:
    """Build an async SQLAlchemy engine bound to the given URL."""
    return create_async_engine(database_url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Return the process-wide async engine, lazily constructed from settings."""
    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is not configured")
    return make_engine(settings.database_url)


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return a cached async_sessionmaker bound to the lazy engine."""
    return async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields an AsyncSession bound to the lazy engine."""
    factory = get_sessionmaker()
    async with factory() as session:
        yield session
