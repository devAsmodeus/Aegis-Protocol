"""HybridPipeline orchestration: parallel fanout, RRF, optional rerank."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from aegis.retrieval import (
    IdentityReranker,
    RetrievalHit,
    RetrievalQuery,
    StaticRetriever,
    content_hash,
)
from aegis.retrieval.pipeline import HybridPipeline


async def test_pipeline_with_no_retrievers_returns_empty() -> None:
    p = HybridPipeline(retrievers=[])
    assert await p.retrieve(RetrievalQuery(text="x")) == []


async def test_pipeline_fuses_two_retrievers() -> None:
    dense = StaticRetriever(
        label="dense",
        chunks=[("shared", 0.9, {}), ("dense_only", 0.7, {})],
    )
    bm25 = StaticRetriever(
        label="bm25",
        chunks=[("shared", 0.95, {}), ("bm25_only", 0.6, {})],
    )
    p = HybridPipeline(retrievers=[dense, bm25], fanout_k=10, final_k=5)
    hits = await p.retrieve(RetrievalQuery(text="q"))
    contents = [h.content for h in hits]
    # "shared" must rank first because it's hit by both retrievers.
    assert contents[0] == "shared"
    assert set(contents) == {"shared", "dense_only", "bm25_only"}
    assert all(h.source == "rrf" for h in hits)


async def test_pipeline_truncates_to_final_k_when_no_reranker() -> None:
    r = StaticRetriever(
        label="dense",
        chunks=[(f"c{i}", 1.0 - i * 0.01, {}) for i in range(20)],
    )
    p = HybridPipeline(retrievers=[r], fanout_k=20, final_k=4)
    hits = await p.retrieve(RetrievalQuery(text="q"))
    assert len(hits) == 4


async def test_pipeline_runs_retrievers_concurrently() -> None:
    @dataclass(slots=True)
    class _SlowRetriever:
        label: str
        chunks: list[tuple[str, float, dict[str, object]]] = field(default_factory=list)
        delay_s: float = 0.05

        async def retrieve(self, query: RetrievalQuery, k: int) -> list[RetrievalHit]:
            await asyncio.sleep(self.delay_s)
            return [
                RetrievalHit(
                    content=text,
                    content_hash=content_hash(text),
                    score=score,
                    source=self.label,
                    metadata=dict(meta),
                )
                for text, score, meta in self.chunks[:k]
            ]

    a = _SlowRetriever(label="a", chunks=[("a", 1.0, {})])
    b = _SlowRetriever(label="b", chunks=[("b", 1.0, {})])
    p = HybridPipeline(retrievers=[a, b], fanout_k=5, final_k=5)
    started = asyncio.get_event_loop().time()
    hits = await p.retrieve(RetrievalQuery(text="q"))
    elapsed = asyncio.get_event_loop().time() - started
    assert len(hits) == 2
    # Sequential would be ~0.10s; parallel should be ≤ ~0.08s with margin.
    assert elapsed < 0.09


async def test_pipeline_invokes_reranker_when_provided() -> None:
    @dataclass(slots=True)
    class _ReverseReranker:
        async def rerank(
            self,
            query: RetrievalQuery,
            hits: list[RetrievalHit],
            k: int,
        ) -> list[RetrievalHit]:
            del query
            return list(reversed(hits))[:k]

    r = StaticRetriever(
        label="dense",
        chunks=[("a", 0.9, {}), ("b", 0.7, {}), ("c", 0.5, {})],
    )
    p = HybridPipeline(retrievers=[r], reranker=_ReverseReranker(), fanout_k=10, final_k=3)
    hits = await p.retrieve(RetrievalQuery(text="q"))
    # Reranker reverses: original RRF order is [a, b, c] → reversed [c, b, a].
    assert [h.content for h in hits] == ["c", "b", "a"]


async def test_pipeline_reranker_can_truncate_below_rrf() -> None:
    r = StaticRetriever(
        label="dense",
        chunks=[("a", 0.9, {}), ("b", 0.7, {}), ("c", 0.5, {})],
    )
    p = HybridPipeline(retrievers=[r], reranker=IdentityReranker(), fanout_k=10, final_k=2)
    hits = await p.retrieve(RetrievalQuery(text="q"))
    assert len(hits) == 2
