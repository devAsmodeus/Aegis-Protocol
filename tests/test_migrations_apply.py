"""Integration: apply migrations to a real Postgres DB and verify the schema.

Marked `integration` — requires `docker compose up -d` and DATABASE_URL set.
"""

from __future__ import annotations

import asyncio

import pytest
import sqlalchemy as sa
from aegis.config import get_settings
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.integration
def test_migrations_apply_to_clean_db() -> None:
    settings = get_settings()
    if settings.database_url is None:
        pytest.skip("DATABASE_URL is not configured")

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")

    async def _list_tables() -> set[str]:
        engine = create_async_engine(settings.database_url)
        async with engine.connect() as conn:
            result = await conn.execute(
                sa.text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'")
            )
            tables = {row[0] for row in result}
        await engine.dispose()
        return tables

    tables = asyncio.run(_list_tables())
    expected = {"tenants", "conversations", "messages", "receipts"}
    assert expected.issubset(tables), f"missing tables: {expected - tables}"
