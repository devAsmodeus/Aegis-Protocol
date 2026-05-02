"""Keeper task registry.

Tasks register by name; the webhook resolves a name to a registered
task and runs it. Lookup is O(1); the registry holds strong references
so a task created in module scope survives the request lifecycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aegis.keeper.tasks import ScheduledTask, TaskResult


@dataclass(slots=True)
class KeeperRegistry:
    """Indexed lookup over :class:`ScheduledTask` instances.

    Attributes:
        _tasks: Internal name → task map. Populated via
            :meth:`register`; tests inspect via :meth:`names`.
    """

    _tasks: dict[str, ScheduledTask] = field(default_factory=dict)

    def register(self, task: ScheduledTask) -> None:
        """Add a task. Re-registering the same name overwrites it."""
        self._tasks[task.name] = task

    def get(self, name: str) -> ScheduledTask | None:
        """Return the task by name, or ``None`` if not registered."""
        return self._tasks.get(name)

    def names(self) -> list[str]:
        """Return the registered task names, sorted for stable output."""
        return sorted(self._tasks.keys())

    async def run(self, name: str) -> TaskResult:
        """Run a single task by name.

        Raises:
            KeyError: If no task is registered under ``name``.
        """
        task = self._tasks.get(name)
        if task is None:
            raise KeyError(name)
        return await task.run()

    async def run_all(self) -> list[TaskResult]:
        """Run every registered task, in name-sorted order."""
        results: list[TaskResult] = []
        for name in self.names():
            results.append(await self._tasks[name].run())
        return results


__all__ = ["KeeperRegistry"]
