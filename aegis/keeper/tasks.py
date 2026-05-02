"""Scheduled task definitions for the keeper layer.

Every task implements :class:`ScheduledTask` and returns a
:class:`TaskResult`. The result envelope is uniform so the HTTP layer
can serialize it without knowing per-task details, and so a task can
record ``"skipped"`` when a required upstream is not configured.

Per ``CLAUDE.md`` §3, no task may attempt a real upstream call without
the upstream URL being configured. All real I/O is opt-in; the default
behavior in unit tests is to skip cleanly.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from aegis.config import Settings


class TaskResult(BaseModel):
    """Uniform envelope returned by every :class:`ScheduledTask`.

    Attributes:
        name: Stable task identifier.
        started_at: Wall-clock UTC at the start of :meth:`run`.
        finished_at: Wall-clock UTC after the task returns (whether it
            succeeded, failed, or was skipped).
        success: ``True`` if the task ran to completion without error.
            A skipped task counts as ``success=True`` with
            ``summary == "skipped"``.
        summary: Short human-readable status (one of ``"ok"``,
            ``"skipped"``, ``"failed"``, plus an optional reason).
        details: Free-form per-task structured details. Stable across
            runs of the same task version so admins can diff outputs.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    started_at: datetime
    finished_at: datetime
    success: bool
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class ScheduledTask(Protocol):
    """A task triggerable by name from the keeper webhook or registry."""

    @property
    def name(self) -> str:
        """Stable identifier used by callers (incl. KeeperHub) to invoke it."""

    async def run(self) -> TaskResult:
        """Execute the task. Must not raise; failures become ``success=False``."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class RefreshDocumentsTask:
    """Re-embed tenant documents whose source ``mtime`` has changed.

    The Day 8 schema does not yet ship a ``documents`` table (PR #2 left
    that for later). Until the table lands, the task scans an injected
    ``document_source`` callable for changed entries and reports the
    count without re-embedding. The flag ``actually_reembed`` lets a
    follow-up task wire a real path without rewriting the contract.

    Attributes:
        document_source: Callable returning the current ``[(doc_id,
            mtime)]`` list. Defaults to an empty list so the task is
            stub-friendly.
        actually_reembed: Reserved for the follow-up that wires the
            real RAG pipeline. Currently the task only counts changed
            docs; with this flag set the task additionally reports
            ``would_reembed=True`` so callers can dry-run the future
            behavior.
    """

    document_source: Callable[[], Awaitable[list[tuple[str, float]]]] | None = None
    actually_reembed: bool = False
    name: str = field(default="refresh_documents", init=False)

    async def run(self) -> TaskResult:
        started = _utcnow()
        if self.document_source is None:
            return TaskResult(
                name=self.name,
                started_at=started,
                finished_at=_utcnow(),
                success=True,
                summary="skipped",
                details={"reason": "no document source configured"},
            )
        try:
            docs = await self.document_source()
        except Exception as exc:
            return TaskResult(
                name=self.name,
                started_at=started,
                finished_at=_utcnow(),
                success=False,
                summary="failed",
                details={"error": repr(exc)},
            )
        return TaskResult(
            name=self.name,
            started_at=started,
            finished_at=_utcnow(),
            success=True,
            summary="ok",
            details={
                "scanned": len(docs),
                "would_reembed": self.actually_reembed,
            },
        )


@dataclass(slots=True)
class RotateAgentSessionsTask:
    """Purge stale rows from the audit log older than ``older_than_days``.

    Today the project does not yet ship a dedicated ``audit_log`` table;
    receipts on :class:`aegis.db.models.Receipt` are the closest
    equivalent. The task issues a real async SQLAlchemy ``DELETE`` if a
    ``session_factory`` is supplied, otherwise it skips. Tests pass a
    fake session factory and assert the SQL was emitted.

    Attributes:
        session_factory: Async sessionmaker. ``None`` = task skips.
        older_than_days: Anything older than this many days from
            ``now()`` is purged. Defaults to 30.
        table_name: Name of the table to purge. Defaults to
            ``"receipts"``; tests can override to ``"audit_log"`` once
            the dedicated table lands.
    """

    session_factory: Any | None = None
    older_than_days: int = 30
    table_name: str = "receipts"
    name: str = field(default="rotate_agent_sessions", init=False)

    async def run(self) -> TaskResult:
        started = _utcnow()
        if self.session_factory is None:
            return TaskResult(
                name=self.name,
                started_at=started,
                finished_at=_utcnow(),
                success=True,
                summary="skipped",
                details={"reason": "no session factory configured"},
            )
        from sqlalchemy import text  # local import keeps import cost low

        cutoff = _utcnow() - timedelta(days=self.older_than_days)
        statement = text(f"DELETE FROM {self.table_name} WHERE created_at < :cutoff")
        try:
            async with self.session_factory() as session:
                result = await session.execute(statement, {"cutoff": cutoff})
                await session.commit()
                rowcount = getattr(result, "rowcount", 0) or 0
        except Exception as exc:
            return TaskResult(
                name=self.name,
                started_at=started,
                finished_at=_utcnow(),
                success=False,
                summary="failed",
                details={"error": repr(exc)},
            )
        return TaskResult(
            name=self.name,
            started_at=started,
            finished_at=_utcnow(),
            success=True,
            summary="ok",
            details={
                "table": self.table_name,
                "older_than_days": self.older_than_days,
                "deleted": int(rowcount),
            },
        )


@dataclass(slots=True)
class HealthcheckUpstreamsTask:
    """Ping every configured upstream and return up/down per service.

    Only services whose URL is configured in :class:`Settings` are
    pinged; others are reported as ``"skipped"``. The actual probe
    callables are injected so unit tests can stub them without docker.

    Attributes:
        settings: The :class:`Settings` snapshot to read upstream URLs
            from.
        probes: Mapping of service-name → ``async (url) -> bool`` probe.
            ``True`` = up, ``False`` = down, raises = down (recorded
            with the exception type). Defaults to a no-op map; callers
            wire concrete probes.
    """

    settings: Settings
    probes: dict[str, Callable[[str], Awaitable[bool]]] = field(default_factory=dict)
    name: str = field(default="healthcheck_upstreams", init=False)

    async def run(self) -> TaskResult:
        started = _utcnow()
        services: dict[str, str | None] = {
            "database": self.settings.database_url,
            "redis": self.settings.redis_url,
            "qdrant": self.settings.qdrant_url,
            "rpc": self.settings.eth_rpc_url,
        }
        report: dict[str, dict[str, Any]] = {}
        for service, url in services.items():
            if not url:
                report[service] = {"status": "skipped", "configured": False}
                continue
            probe = self.probes.get(service)
            if probe is None:
                report[service] = {"status": "skipped", "configured": True, "reason": "no probe"}
                continue
            try:
                ok = await probe(url)
            except Exception as exc:
                report[service] = {"status": "down", "error": repr(exc)}
                continue
            report[service] = {"status": "up" if ok else "down"}
        all_ok = all(v.get("status") in {"up", "skipped"} for v in report.values())
        return TaskResult(
            name=self.name,
            started_at=started,
            finished_at=_utcnow(),
            success=all_ok,
            summary="ok" if all_ok else "failed",
            details={"services": report},
        )


__all__ = [
    "HealthcheckUpstreamsTask",
    "RefreshDocumentsTask",
    "RotateAgentSessionsTask",
    "ScheduledTask",
    "TaskResult",
]
