"""Deterministic LLM stubs for unit-testing the runtime.

Real cloud-LLM adapters (e.g. 0G Compute TEE) live elsewhere. These
stubs let us exercise :class:`~aegis.agent.runtime.Runtime` end-to-end
without a network or model.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from aegis.agent.protocol import Tool
from aegis.agent.types import LLMOutput, ToolCall


@dataclass(slots=True)
class EchoLLM:
    """Returns the last user message verbatim. Never calls a tool."""

    model_id: str = "echo-llm"

    async def complete(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[Tool],
    ) -> LLMOutput:
        del tools
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return LLMOutput(text=str(msg.get("content", "")))
        return LLMOutput(text="")


@dataclass(slots=True)
class StaticToolPlanLLM:
    """Plays back a scripted plan, one entry per :meth:`complete` call.

    Each entry is either:
        * a :class:`ToolCall` → emitted as a single tool call, or
        * a ``str`` → emitted as the final ``text``.

    Once the plan is exhausted, returns an empty :class:`LLMOutput`.
    Used in :file:`tests/test_agent_runtime.py` to drive the loop
    deterministically.
    """

    plan: list[ToolCall | str] = field(default_factory=list)
    model_id: str = "static-plan"
    _cursor: int = 0

    async def complete(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[Tool],
    ) -> LLMOutput:
        del messages, tools
        if self._cursor >= len(self.plan):
            return LLMOutput()
        entry = self.plan[self._cursor]
        self._cursor += 1
        if isinstance(entry, ToolCall):
            return LLMOutput(tool_calls=(entry,))
        return LLMOutput(text=entry)
