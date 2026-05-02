"""KeeperHub-style scheduled task infrastructure.

This package provides:

* :class:`~aegis.keeper.tasks.ScheduledTask` — :class:`~typing.Protocol`
  for any task triggerable by an external cron caller (KeeperHub) or an
  internal self-test sweep.
* :class:`~aegis.keeper.tasks.TaskResult` — uniform Pydantic envelope
  every task returns, so the API can serialize results without knowing
  per-task details.
* Concrete tasks:

  * :class:`~aegis.keeper.tasks.RefreshDocumentsTask` — re-embed tenant
    documents whose source ``mtime`` changed.
  * :class:`~aegis.keeper.tasks.RotateAgentSessionsTask` — purge stale
    audit rows older than ``older_than_days``.
  * :class:`~aegis.keeper.tasks.HealthcheckUpstreamsTask` — ping the
    configured upstreams (DB, Redis, Qdrant, RPC) and report up/down.
* :class:`~aegis.keeper.registry.KeeperRegistry` — register / lookup /
  run by name.
* :func:`~aegis.keeper.runner.run_task_by_name` — entry point used by
  the ``/v1/keeper`` webhook route.

Per ``CLAUDE.md`` §3, anything that hits a real upstream is gated on
the upstream URL being configured; otherwise the task records
``"skipped"``. Tests run without docker.
"""

from aegis.keeper.registry import KeeperRegistry
from aegis.keeper.runner import run_task_by_name
from aegis.keeper.tasks import (
    HealthcheckUpstreamsTask,
    RefreshDocumentsTask,
    RotateAgentSessionsTask,
    ScheduledTask,
    TaskResult,
)

__all__ = [
    "HealthcheckUpstreamsTask",
    "KeeperRegistry",
    "RefreshDocumentsTask",
    "RotateAgentSessionsTask",
    "ScheduledTask",
    "TaskResult",
    "run_task_by_name",
]
