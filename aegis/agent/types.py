"""Core agent data types.

Frozen, slotted dataclasses so they are cheap to construct, hashable
where useful, and impossible to accidentally mutate. All identifiers
are plain `str` / `UUID`; payloads live in `dict[str, Any]` so callers
keep flexibility without coupling the runtime to a specific JSON
schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AgentRequest:
    """User-facing input to a single :class:`Runtime.run` invocation."""

    text: str
    tenant_id: str | None = None
    conversation_id: UUID | None = None
    external_user_id: str | None = None


@dataclass(frozen=True, slots=True)
class AgentResponse:
    """Final reply produced by the runtime.

    Attributes:
        text: Natural-language answer.
        retrieval_hashes: sha256 content-hashes of every retrieval hit
            that influenced the answer. Per ``CLAUDE.md`` §3, receipts
            store these hashes — not Qdrant point IDs.
        tools_used: Ordered tuple of tool names invoked during the
            run. Empty if the model produced text directly.
        model_id: Free-form model identifier echoed from the LLM
            client. Recorded in the receipt for reproducibility.
    """

    text: str
    retrieval_hashes: tuple[str, ...] = ()
    tools_used: tuple[str, ...] = ()
    model_id: str = ""


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A single tool invocation requested by the model."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Output of a tool, fed back into the LLM as context."""

    name: str
    output: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LLMOutput:
    """Result of one :meth:`LLMClient.complete` call.

    Exactly one of ``text`` and ``tool_calls`` should be populated:

    * ``text`` is non-empty → final answer.
    * ``tool_calls`` is non-empty → dispatch tools, loop again.
    """

    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True, slots=True)
class ReceiptDraft:
    """Inputs the runtime passes to a :class:`ReceiptSink`.

    The sink decides how to persist the draft (DB row, 0G DA tx, log
    line, …). Hashes are computed by the runtime so the sink doesn't
    need to know the canonical hash function.
    """

    tenant_id: str | None
    conversation_id: UUID | None
    input_hash: str
    output_hash: str
    model_id: str
    retrieval_hashes: tuple[str, ...]
    tools_used: tuple[str, ...]
    payload: dict[str, Any] = field(default_factory=dict)
