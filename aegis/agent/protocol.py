"""Background interfaces consumed by :class:`Runtime`.

Per ``CLAUDE.md`` §4 heuristic, these are :class:`~typing.Protocol` s
with deterministic stub implementations in
:mod:`aegis.agent.stubs` so the e2e tool-loop is exercisable without
docker, real LLMs, or a database.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from aegis.agent.types import LLMOutput, ReceiptDraft, ToolCall, ToolResult


@runtime_checkable
class LLMClient(Protocol):
    """Produces either a final text reply or a tool call.

    Implementations:
        * :class:`~aegis.agent.stubs.EchoLLM` — deterministic test stub.
        * :class:`~aegis.agent.stubs.StaticToolPlanLLM` — drives the
          tool-loop in tests.
        * Real cloud-LLM adapters (added later, e.g. 0G Compute TEE).
    """

    @property
    def model_id(self) -> str:
        """Free-form model identifier recorded in receipts."""

    async def complete(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[Tool],
    ) -> LLMOutput:
        """Take chat history + available tools, return next step."""


@runtime_checkable
class Tool(Protocol):
    """A capability the agent can invoke during a run."""

    @property
    def name(self) -> str:
        """Stable identifier the LLM uses to refer to this tool."""

    @property
    def description(self) -> str:
        """Human-readable purpose, exposed to the LLM."""

    @property
    def json_schema(self) -> dict[str, Any]:
        """JSON-schema describing the ``arguments`` dict."""

    async def call(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute the tool. Result text is fed back into the LLM."""


@runtime_checkable
class ReceiptSink(Protocol):
    """Persists a :class:`ReceiptDraft`.

    The runtime calls :meth:`record` exactly once per reply, before
    returning. Implementations may write to Postgres, 0G DA, both, or
    a no-op log.
    """

    async def record(self, draft: ReceiptDraft) -> None:
        """Persist the receipt. Must not raise on duplicate hashes."""


__all__ = [
    "LLMClient",
    "ReceiptSink",
    "Tool",
    "ToolCall",
    "ToolResult",
]
