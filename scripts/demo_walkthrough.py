"""End-to-end demo walkthrough using stubs only.

Run with::

    uv run python -m scripts.demo_walkthrough

The script orchestrates the existing project stubs to print a captioned
transcript that mirrors what a judge would see in the live demo:

1. Registry (PR #2): register an agent in :class:`StubAegisRegistry`.
2. ENS (PR #1): forward-resolve the agent's ENS subname.
3. Tool-loop (Day 4): run a user question end-to-end through the agent
   runtime with the RAG tool plugged in.
4. Receipt (Day 4): show the content-hash receipt drafted by the
   runtime.
5. Keeper (Day 8): run the healthcheck task, surface its result.

No network, no docker, no keys. Every line is annotated so the output
doubles as a demo script.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from uuid import uuid4

from aegis.agent.runtime import Runtime
from aegis.agent.stubs import StaticToolPlanLLM
from aegis.agent.tools.rag import RagSearchTool
from aegis.agent.types import AgentRequest, ReceiptDraft, ToolCall
from aegis.chain.registry import StubAegisRegistry
from aegis.channels.memory import InMemoryChannel
from aegis.config import Settings
from aegis.keeper.tasks import HealthcheckUpstreamsTask
from aegis.rag.service import RagService
from aegis.retrieval.pipeline import HybridPipeline
from aegis.retrieval.stubs import StaticRetriever


@dataclass(slots=True)
class _CaptureSink:
    """Trivial :class:`ReceiptSink` that just remembers the last draft."""

    drafts: list[ReceiptDraft] = field(default_factory=list)

    async def record(self, draft: ReceiptDraft) -> None:
        self.drafts.append(draft)


def _print(label: str, body: object) -> None:
    """Pretty-print one demo step with a label."""
    print(f"\n>>> {label}")
    if isinstance(body, str):
        for line in body.splitlines() or [""]:
            print(f"    {line}")
    else:
        print(f"    {body}")


def _format_tools(tools: Iterable[str]) -> str:
    return ", ".join(tools) or "(none)"


async def run_demo() -> dict[str, object]:
    """Run the whole walkthrough and return a summary dict.

    The summary is also useful for tests that want to assert outcomes
    instead of parsing stdout.
    """
    print("=" * 72)
    print("  Aegis Protocol — demo walkthrough (stubs only, no network)")
    print("=" * 72)

    # --- step 1: register an agent on the (stub) on-chain registry ---
    registry = StubAegisRegistry()
    ens_subname = "support.acme.eth"
    kb_cid_hash = "0x" + "ab" * 32
    await registry.register(ens_subname, kb_cid_hash)
    record = await registry.get(ens_subname)
    assert record is not None  # mypy: registered above
    _print(
        "Step 1 — Registry: register agent (PR #2 / KeeperHub-adjacent)",
        f"ENS subname: {record.ens_subname}\n"
        f"owner:       {record.owner}\n"
        f"active:      {record.active}",
    )

    # --- step 2: end-to-end tool-loop run ---
    #
    # The rag_search tool is plugged in so the demo proves the agent can
    # cite tenant-scoped docs. We use stub retrievers so the demo runs
    # without docker.
    retriever = StaticRetriever(
        label="acme-docs",
        chunks=[
            (
                "If a contract calls approve() with the maximum uint256 value, "
                "treat it as an unlimited allowance and warn the user.",
                0.99,
                {"source": "security-faq.md"},
            )
        ],
    )
    pipeline = HybridPipeline(retrievers=[retriever], reranker=None, final_k=2)
    rag_tool = RagSearchTool(service=RagService(pipeline=pipeline), top_k=2)
    plan = [
        ToolCall(name="rag_search", arguments={"query": "what is unlimited approval"}),
        "Treat unlimited token allowances as a red flag and never auto-sign them.",
    ]
    sink = _CaptureSink()
    runtime = Runtime(
        llm=StaticToolPlanLLM(plan=plan),
        tools=[rag_tool],
        receipt_sink=sink,
        max_tool_calls=2,
    )
    request = AgentRequest(
        text="What is unlimited approval?",
        tenant_id="acme",
        conversation_id=uuid4(),
        external_user_id="user-007",
    )
    response = await runtime.run(request)
    _print(
        "Step 2 — Channel + Agent runtime (Day 4/5)",
        f"user:      {request.text}\n"
        f"agent:     {response.text}\n"
        f"tools:     {_format_tools(response.tools_used)}\n"
        f"model:     {response.model_id}",
    )

    # --- step 3: receipt with content-hashes ---
    last_receipt = sink.drafts[-1]
    _print(
        "Step 3 — Receipt (Day 4 — verifiability)",
        f"input_hash:    {last_receipt.input_hash[:16]}…\n"
        f"output_hash:   {last_receipt.output_hash[:16]}…\n"
        f"retrieval_ids: {list(last_receipt.retrieval_hashes)}\n"
        f"tools_used:    {list(last_receipt.tools_used)}",
    )

    # --- step 4: ENS verifyability ---
    is_active = await registry.is_active(ens_subname)
    _print(
        "Step 4 — ENS verifyability (Day 6/7)",
        f"AegisRegistry.isActive('{ens_subname}'): {is_active}",
    )

    # --- step 5: keeper task ---
    settings = Settings(database_url=None, redis_url=None, qdrant_url=None, eth_rpc_url=None)
    keeper_task = HealthcheckUpstreamsTask(settings=settings)
    keeper_result = await keeper_task.run()
    _print(
        "Step 5 — Keeper task (Day 8 — KeeperHub track)",
        f"task:    {keeper_result.name}\n"
        f"summary: {keeper_result.summary}\n"
        f"details: {keeper_result.details}",
    )

    # --- bonus: in-memory channel round-trip ---
    channel = InMemoryChannel()
    channel.inject("hello", external_user_id="user-007", tenant_id="acme")

    async def echo_handler(incoming):
        from aegis.channels.base import OutgoingMessage

        return OutgoingMessage(
            text=f"echo: {incoming.text}",
            channel=incoming.channel,
            conversation_external_id=incoming.conversation_external_id,
        )

    await channel.start(echo_handler)
    _print(
        "Bonus — In-memory channel round-trip (Day 5)",
        f"outbox: {[m.text for m in channel.outbox]}",
    )

    print("\n" + "=" * 72)
    print("  Demo complete — every step ran offline. Tests assert each result.")
    print("=" * 72)

    return {
        "registry_active": is_active,
        "agent_text": response.text,
        "tools_used": list(response.tools_used),
        "receipt_input_hash": last_receipt.input_hash,
        "receipt_output_hash": last_receipt.output_hash,
        "keeper_summary": keeper_result.summary,
    }


def main() -> int:
    """CLI entry point used by ``python -m scripts.demo_walkthrough``."""
    asyncio.run(run_demo())
    return 0


if __name__ == "__main__":  # pragma: no cover — CLI guard
    sys.exit(main())
