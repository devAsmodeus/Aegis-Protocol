"""Runtime tool-loop tests.

Exercises Runtime end-to-end with deterministic stubs:
* pure-text response,
* single tool call → text,
* tool-budget exhaustion,
* unknown tool error,
* receipt content (hashes, model_id, ordered tools_used).
"""

from __future__ import annotations

import hashlib
from typing import Any, ClassVar

import pytest
from aegis.agent.errors import UnknownToolError
from aegis.agent.protocol import ReceiptSink
from aegis.agent.runtime import Runtime
from aegis.agent.stubs import EchoLLM, StaticToolPlanLLM
from aegis.agent.tools.rag import RagSearchTool
from aegis.agent.types import AgentRequest, ReceiptDraft, ToolCall, ToolResult
from aegis.rag.service import RagService
from aegis.retrieval.pipeline import HybridPipeline
from aegis.retrieval.stubs import StaticRetriever


class _RecordingSink(ReceiptSink):
    def __init__(self) -> None:
        self.drafts: list[ReceiptDraft] = []

    async def record(self, draft: ReceiptDraft) -> None:
        self.drafts.append(draft)


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@pytest.mark.asyncio
async def test_runtime_pure_text_no_tools() -> None:
    sink = _RecordingSink()
    rt = Runtime(llm=EchoLLM(), tools=(), receipt_sink=sink)

    resp = await rt.run(AgentRequest(text="hello world", tenant_id="t1"))

    assert resp.text == "hello world"
    assert resp.tools_used == ()
    assert resp.retrieval_hashes == ()
    assert resp.model_id == "echo-llm"
    assert len(sink.drafts) == 1
    draft = sink.drafts[0]
    assert draft.input_hash == _sha("hello world")
    assert draft.output_hash == _sha("hello world")
    assert draft.tenant_id == "t1"


@pytest.mark.asyncio
async def test_runtime_dispatches_single_tool_then_replies() -> None:
    sink = _RecordingSink()
    chunks = [
        ("Aegis is an ENS-verified support agent.", 1.0, {}),
        ("It runs inference inside a 0G TEE.", 0.9, {}),
    ]
    pipeline = HybridPipeline(retrievers=[StaticRetriever("dense", chunks)], fanout_k=10, final_k=2)
    tool = RagSearchTool(service=RagService(pipeline=pipeline), top_k=2)

    plan = [
        ToolCall(name="rag_search", arguments={"query": "what is Aegis?"}),
        "Aegis is an ENS-verified support agent that runs in a TEE.",
    ]
    rt = Runtime(llm=StaticToolPlanLLM(plan=plan), tools=(tool,), receipt_sink=sink)

    resp = await rt.run(AgentRequest(text="what is Aegis?"))

    assert resp.tools_used == ("rag_search",)
    assert len(resp.retrieval_hashes) == 2
    assert resp.text.startswith("Aegis is an ENS-verified support agent")
    # receipt mirrors the response
    assert sink.drafts[0].tools_used == ("rag_search",)
    assert sink.drafts[0].retrieval_hashes == resp.retrieval_hashes
    assert sink.drafts[0].model_id == "static-plan"


@pytest.mark.asyncio
async def test_runtime_unknown_tool_raises() -> None:
    plan = [ToolCall(name="does_not_exist", arguments={})]
    rt = Runtime(
        llm=StaticToolPlanLLM(plan=plan),
        tools=(),
        receipt_sink=_RecordingSink(),
    )

    with pytest.raises(UnknownToolError):
        await rt.run(AgentRequest(text="x"))


@pytest.mark.asyncio
async def test_runtime_tool_budget_exhaustion() -> None:
    """If the plan keeps issuing tool calls past max_tool_calls, the
    runtime breaks with a deterministic message and still writes a
    receipt."""
    sink = _RecordingSink()

    class NoOpTool:
        name = "noop"
        description = "always returns ok"
        json_schema: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}

        async def call(self, arguments: dict[str, Any]) -> ToolResult:
            del arguments
            return ToolResult(name="noop", output="ok")

    plan: list[ToolCall | str] = [ToolCall(name="noop") for _ in range(10)]
    rt = Runtime(
        llm=StaticToolPlanLLM(plan=plan),
        tools=(NoOpTool(),),
        receipt_sink=sink,
        max_tool_calls=2,
    )

    resp = await rt.run(AgentRequest(text="loop forever"))

    assert resp.text == "(tool budget exhausted)"
    assert len(resp.tools_used) == 2
    assert sink.drafts[0].output_hash == _sha("(tool budget exhausted)")


@pytest.mark.asyncio
async def test_runtime_dedupes_repeated_content_hashes() -> None:
    """Two tool calls returning the same chunk should not double-count
    the hash in the receipt."""
    sink = _RecordingSink()

    class HashTool:
        name = "ht"
        description = "echoes a fixed hash"
        json_schema: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}

        async def call(self, arguments: dict[str, Any]) -> ToolResult:
            del arguments
            return ToolResult(name="ht", output="x", metadata={"content_hashes": ("h1",)})

    plan: list[ToolCall | str] = [
        ToolCall(name="ht"),
        ToolCall(name="ht"),
        "done",
    ]
    rt = Runtime(
        llm=StaticToolPlanLLM(plan=plan),
        tools=(HashTool(),),
        receipt_sink=sink,
        max_tool_calls=4,
    )

    resp = await rt.run(AgentRequest(text="q"))

    assert resp.retrieval_hashes == ("h1",)
    assert resp.tools_used == ("ht", "ht")
