"""``/v1/keeper`` router — KeeperHub-style scheduled task webhook.

Two endpoints:

* ``GET /v1/keeper/tasks`` — read-only metadata listing registered task
  names. No auth.
* ``POST /v1/keeper/tasks/{name}/run`` — run a task. Authenticated via
  HMAC-SHA256 over the raw body. Refuses with 503 if the signing secret
  is not configured (per ``CLAUDE.md`` §3 — never an open default).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from aegis.api.dependencies import (
    KeeperRegistryDep,
    verify_keeper_signature,
)
from aegis.keeper import TaskResult

router = APIRouter(prefix="/v1/keeper", tags=["keeper"])


class TaskList(BaseModel):
    """Response payload for ``GET /v1/keeper/tasks``."""

    tasks: list[str]


@router.get("/tasks", response_model=TaskList)
async def list_tasks(registry: KeeperRegistryDep) -> TaskList:
    """List registered task names. Read-only; no auth."""
    return TaskList(tasks=registry.names())


@router.post(
    "/tasks/{name}/run",
    response_model=TaskResult,
    dependencies=[Depends(verify_keeper_signature)],
)
async def run_task(name: str, registry: KeeperRegistryDep) -> TaskResult:
    """Run a registered task. HMAC-SHA256 auth required."""
    task = registry.get(name)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"task {name!r} is not registered",
        )
    return await task.run()


__all__ = ["router"]
