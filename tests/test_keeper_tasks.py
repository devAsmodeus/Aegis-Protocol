"""Unit tests for `aegis.keeper.tasks`.

No docker, no real DB. The healthcheck task is exercised via injected
async probes; the rotate task uses a fake `async_sessionmaker`-shaped
factory; the refresh task gets an injected document source.
"""

from __future__ import annotations

from typing import Any

import pytest
from aegis.config import Settings
from aegis.keeper.tasks import (
    HealthcheckUpstreamsTask,
    RefreshDocumentsTask,
    RotateAgentSessionsTask,
    TaskResult,
)


@pytest.mark.asyncio
async def test_refresh_documents_skips_without_source() -> None:
    task = RefreshDocumentsTask()
    result = await task.run()
    assert isinstance(result, TaskResult)
    assert result.name == "refresh_documents"
    assert result.success is True
    assert result.summary == "skipped"


@pytest.mark.asyncio
async def test_refresh_documents_counts_changed_docs() -> None:
    async def docs() -> list[tuple[str, float]]:
        return [("doc1", 1.0), ("doc2", 2.0), ("doc3", 3.0)]

    task = RefreshDocumentsTask(document_source=docs, actually_reembed=True)
    result = await task.run()
    assert result.success is True
    assert result.summary == "ok"
    assert result.details == {"scanned": 3, "would_reembed": True}


@pytest.mark.asyncio
async def test_refresh_documents_records_failure() -> None:
    async def boom() -> list[tuple[str, float]]:
        raise RuntimeError("kaboom")

    task = RefreshDocumentsTask(document_source=boom)
    result = await task.run()
    assert result.success is False
    assert result.summary == "failed"
    assert "kaboom" in result.details["error"]


class _FakeResult:
    rowcount = 7


class _FakeSession:
    def __init__(self, log: list[tuple[str, Any]]) -> None:
        self._log = log

    async def __aenter__(self) -> _FakeSession:
        self._log.append(("enter", None))
        return self

    async def __aexit__(self, *exc: Any) -> None:
        self._log.append(("exit", None))

    async def execute(self, statement: Any, params: Any) -> _FakeResult:
        self._log.append(("execute", (str(statement), params)))
        return _FakeResult()

    async def commit(self) -> None:
        self._log.append(("commit", None))


def _factory(log: list[tuple[str, Any]]):
    def _build() -> _FakeSession:
        return _FakeSession(log)

    return _build


@pytest.mark.asyncio
async def test_rotate_skips_without_factory() -> None:
    task = RotateAgentSessionsTask()
    result = await task.run()
    assert result.success is True
    assert result.summary == "skipped"


@pytest.mark.asyncio
async def test_rotate_emits_delete_and_reports_rowcount() -> None:
    log: list[tuple[str, Any]] = []
    task = RotateAgentSessionsTask(
        session_factory=_factory(log),
        older_than_days=14,
        table_name="receipts",
    )
    result = await task.run()
    assert result.success is True
    assert result.summary == "ok"
    assert result.details == {"table": "receipts", "older_than_days": 14, "deleted": 7}
    actions = [name for name, _ in log]
    assert actions == ["enter", "execute", "commit", "exit"]
    _, payload = log[1]
    sql_text, params = payload
    assert "DELETE FROM receipts" in sql_text
    assert "cutoff" in params


@pytest.mark.asyncio
async def test_healthcheck_skips_unconfigured_services() -> None:
    settings = Settings(
        database_url=None,
        redis_url=None,
        qdrant_url=None,
        eth_rpc_url=None,
    )
    task = HealthcheckUpstreamsTask(settings=settings)
    result = await task.run()
    assert result.success is True
    services = result.details["services"]
    assert all(v["status"] == "skipped" for v in services.values())


@pytest.mark.asyncio
async def test_healthcheck_reports_up_and_down() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://x",
        redis_url="redis://x",
        qdrant_url=None,  # skipped
        eth_rpc_url="https://rpc",
    )

    async def up(_url: str) -> bool:
        return True

    async def down(_url: str) -> bool:
        return False

    async def boom(_url: str) -> bool:
        raise RuntimeError("rpc-fail")

    task = HealthcheckUpstreamsTask(
        settings=settings,
        probes={"database": up, "redis": down, "rpc": boom},
    )
    result = await task.run()
    services = result.details["services"]
    assert services["database"]["status"] == "up"
    assert services["redis"]["status"] == "down"
    assert services["qdrant"]["status"] == "skipped"
    assert services["rpc"]["status"] == "down"
    assert "rpc-fail" in services["rpc"]["error"]
    assert result.success is False  # any "down" flips success


@pytest.mark.asyncio
async def test_healthcheck_skips_when_probe_missing() -> None:
    settings = Settings(database_url="postgresql+asyncpg://x")
    task = HealthcheckUpstreamsTask(settings=settings, probes={})
    result = await task.run()
    services = result.details["services"]
    assert services["database"] == {
        "status": "skipped",
        "configured": True,
        "reason": "no probe",
    }
