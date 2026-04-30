"""Unit tests for the `rag_search` tool."""

from __future__ import annotations

import pytest
from aegis.agent.tools.rag import RagSearchTool
from aegis.rag.service import RagService
from aegis.retrieval.pipeline import HybridPipeline
from aegis.retrieval.stubs import StaticRetriever
from aegis.retrieval.types import content_hash


@pytest.mark.asyncio
async def test_rag_search_tool_returns_joined_hits_and_hashes() -> None:
    chunks = [
        ("Aegis verifies inference inside a TEE.", 0.9, {}),
        ("ENS subnames are managed via AegisRegistry.", 0.8, {}),
        ("Receipts are stored on 0G DA.", 0.7, {}),
    ]
    pipeline = HybridPipeline(
        retrievers=[StaticRetriever("dense", chunks)],
        fanout_k=10,
        final_k=3,
    )
    service = RagService(pipeline=pipeline)
    tool = RagSearchTool(service=service, top_k=2)

    result = await tool.call({"query": "What is Aegis?"})

    assert tool.name == "rag_search"
    assert "TEE" in result.output
    assert "AegisRegistry" in result.output
    # joined exactly, in pipeline order
    assert result.output.startswith("Aegis verifies inference inside a TEE.")
    # content-hashes echoed for receipt construction
    assert result.metadata["content_hashes"] == (
        content_hash("Aegis verifies inference inside a TEE."),
        content_hash("ENS subnames are managed via AegisRegistry."),
    )
    # Pipeline runs RRF, so each hit's `source` becomes "rrf".
    assert result.metadata["sources"] == ("rrf", "rrf")


@pytest.mark.asyncio
async def test_rag_search_tool_passes_tenant_through() -> None:
    captured: dict[str, object] = {}

    class Spy(StaticRetriever):
        async def retrieve(self, query, k):  # type: ignore[override]
            captured["tenant"] = query.tenant_id
            return await super().retrieve(query, k)

    pipeline = HybridPipeline(retrievers=[Spy("dense", [("x", 1.0, {})])])
    tool = RagSearchTool(service=RagService(pipeline=pipeline))

    await tool.call({"query": "x", "tenant_id": "t-99"})

    assert captured["tenant"] == "t-99"


def test_rag_search_tool_json_schema_requires_query() -> None:
    tool = RagSearchTool(service=RagService(pipeline=HybridPipeline(retrievers=[])))

    schema = tool.json_schema

    assert schema["required"] == ["query"]
    assert "query" in schema["properties"]
