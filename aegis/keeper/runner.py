"""Entry point for the keeper webhook.

Wraps :meth:`KeeperRegistry.run` with a signing-secret precondition.
A missing secret is treated as a misconfiguration, not an open door —
the caller (typically the FastAPI route) raises HTTP 503 in that case.

Per ``CLAUDE.md`` §3 the keeper webhook must never default to open;
this module is the single place that enforces it.
"""

from __future__ import annotations

from aegis.keeper.registry import KeeperRegistry
from aegis.keeper.tasks import TaskResult


class KeeperNotConfiguredError(RuntimeError):
    """Raised when the keeper webhook is invoked without a signing secret."""


class KeeperTaskNotFoundError(KeyError):
    """Raised when the requested task name is not registered."""


async def run_task_by_name(
    name: str,
    registry: KeeperRegistry,
    *,
    signing_secret: str | None,
) -> TaskResult:
    """Run a task by name after verifying the signing secret is set.

    Args:
        name: Registered task name.
        registry: Source of truth for which tasks exist.
        signing_secret: The HMAC secret the webhook authenticates
            against. If ``None`` or empty, this function refuses to run
            — the route should map that to HTTP 503.

    Raises:
        KeeperNotConfiguredError: ``signing_secret`` is missing.
        KeeperTaskNotFoundError: ``name`` is not registered.
    """
    if not signing_secret:
        raise KeeperNotConfiguredError(
            "keeper_signing_secret is not configured; refusing to run tasks"
        )
    task = registry.get(name)
    if task is None:
        raise KeeperTaskNotFoundError(name)
    return await task.run()


__all__ = [
    "KeeperNotConfiguredError",
    "KeeperTaskNotFoundError",
    "run_task_by_name",
]
