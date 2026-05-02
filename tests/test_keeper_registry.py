"""Unit tests for `aegis.keeper.registry` and `aegis.keeper.runner`."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest
from aegis.keeper.registry import KeeperRegistry
from aegis.keeper.runner import (
    KeeperNotConfiguredError,
    KeeperTaskNotFoundError,
    run_task_by_name,
)
from aegis.keeper.tasks import TaskResult


@dataclass(slots=True)
class _StubTask:
    name: str = "stub"
    runs: int = field(default=0)

    async def run(self) -> TaskResult:
        self.runs += 1
        now = datetime.now(UTC)
        return TaskResult(
            name=self.name,
            started_at=now,
            finished_at=now,
            success=True,
            summary="ok",
            details={"calls": self.runs},
        )


@pytest.mark.asyncio
async def test_registry_register_and_run() -> None:
    reg = KeeperRegistry()
    task = _StubTask(name="alpha")
    reg.register(task)
    assert reg.names() == ["alpha"]
    assert reg.get("alpha") is task
    result = await reg.run("alpha")
    assert result.name == "alpha"
    assert task.runs == 1


@pytest.mark.asyncio
async def test_registry_run_unknown_raises_keyerror() -> None:
    reg = KeeperRegistry()
    with pytest.raises(KeyError):
        await reg.run("nope")


@pytest.mark.asyncio
async def test_registry_run_all_in_sorted_order() -> None:
    reg = KeeperRegistry()
    reg.register(_StubTask(name="zeta"))
    reg.register(_StubTask(name="alpha"))
    reg.register(_StubTask(name="mid"))
    results = await reg.run_all()
    assert [r.name for r in results] == ["alpha", "mid", "zeta"]


@pytest.mark.asyncio
async def test_runner_refuses_without_signing_secret() -> None:
    reg = KeeperRegistry()
    reg.register(_StubTask(name="alpha"))
    with pytest.raises(KeeperNotConfiguredError):
        await run_task_by_name("alpha", reg, signing_secret=None)
    with pytest.raises(KeeperNotConfiguredError):
        await run_task_by_name("alpha", reg, signing_secret="")


@pytest.mark.asyncio
async def test_runner_unknown_task_raises_not_found() -> None:
    reg = KeeperRegistry()
    with pytest.raises(KeeperTaskNotFoundError):
        await run_task_by_name("nope", reg, signing_secret="s3cr3t")


@pytest.mark.asyncio
async def test_runner_runs_with_signing_secret() -> None:
    reg = KeeperRegistry()
    task = _StubTask(name="alpha")
    reg.register(task)
    result = await run_task_by_name("alpha", reg, signing_secret="s3cr3t")
    assert result.success is True
    assert task.runs == 1
