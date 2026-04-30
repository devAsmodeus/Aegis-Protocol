"""Unit tests for `aegis.rag.service.RagService`.

These tests exercise the RAG service against the deterministic in-memory
stubs in `aegis.retrieval.stubs` — no Qdrant, no FastEmbed, no docker.
"""

from __future__ import annotations

import pytest
from aegis.rag.service import RagService
from aegis.retrieval.pipeline import HybridPipeline
from aegis.retrieval.stubs import IdentityReranker, StaticRetriever
from aegis.retrieval.types import RetrievalQuery


@pytest.mark.asyncio
async def test_search_returns_topk_from_pipeline() -> None:
    chunks = [
        ("alpha", 0.9, {"tenant": "t1"}),
        ("beta", 0.8, {"tenant": "t1"}),
        ("gamma", 0.7, {"tenant": "t1"}),
    ]
    pipeline = HybridPipeline(
        retrievers=[StaticRetriever("dense", chunks)],
        reranker=IdentityReranker(),
        fanout_k=10,
        final_k=10,
    )
    service = RagService(pipeline=pipeline)

    hits = await service.search(text="anything", tenant_id="t1", k=2)

    assert len(hits) == 2
    assert {h.content for h in hits} == {"alpha", "beta"}


@pytest.mark.asyncio
async def test_search_passes_tenant_and_filters_to_pipeline() -> None:
    """Service must propagate `tenant_id` and `filters` into `RetrievalQuery`."""
    captured: list[RetrievalQuery] = []

    class Spy:
        async def retrieve(self, query: RetrievalQuery, k: int) -> list:
            captured.append(query)
            return []

    pipeline = HybridPipeline(retrievers=[Spy()])
    service = RagService(pipeline=pipeline)

    await service.search(
        text="hi",
        tenant_id="tenant-42",
        filters={"lang": "en"},
        k=3,
    )

    assert len(captured) == 1
    assert captured[0].text == "hi"
    assert captured[0].tenant_id == "tenant-42"
    assert captured[0].filters == {"lang": "en"}


@pytest.mark.asyncio
async def test_search_empty_pipeline_returns_empty_list() -> None:
    service = RagService(pipeline=HybridPipeline(retrievers=[]))

    hits = await service.search(text="anything")

    assert hits == []


@pytest.mark.asyncio
async def test_search_default_k_uses_pipeline_final_k() -> None:
    chunks = [(f"c{i}", float(10 - i), {}) for i in range(5)]
    pipeline = HybridPipeline(
        retrievers=[StaticRetriever("dense", chunks)],
        fanout_k=10,
        final_k=3,
    )
    service = RagService(pipeline=pipeline)

    hits = await service.search(text="x")

    assert len(hits) == 3
    assert [h.content for h in hits] == ["c0", "c1", "c2"]
