"""Hybrid retrieval pipeline.

Fans out a query to N retrievers in parallel, fuses with RRF, optionally
reranks. The pipeline is deliberately I/O-shape agnostic — it consumes
the `Retriever` and `Reranker` `Protocol`s, so the same orchestration is
exercised by stub-based unit tests and Qdrant-backed e2e tests.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from aegis.retrieval.protocol import Reranker, Retriever
from aegis.retrieval.rrf import reciprocal_rank_fusion
from aegis.retrieval.types import RetrievalHit, RetrievalQuery


@dataclass(slots=True)
class HybridPipeline:
    """Runs retrievers concurrently, fuses, optionally reranks.

    Attributes:
        retrievers: All retrievers fan out in parallel via `asyncio.gather`.
        reranker: Optional final-stage reorderer (e.g. cross-encoder).
        fanout_k: Per-retriever candidate budget. Larger = better recall,
            higher latency. Reasonable default: ``50``.
        final_k: How many hits the pipeline returns.
        rrf_k_const: RRF constant. ``60`` is canonical.
    """

    retrievers: Sequence[Retriever]
    reranker: Reranker | None = None
    fanout_k: int = 50
    final_k: int = 10
    rrf_k_const: int = 60

    async def retrieve(self, query: RetrievalQuery) -> list[RetrievalHit]:
        if not self.retrievers:
            return []
        candidate_lists = await asyncio.gather(
            *(r.retrieve(query, self.fanout_k) for r in self.retrievers)
        )
        fused = reciprocal_rank_fusion(
            candidate_lists,
            k_const=self.rrf_k_const,
            limit=None if self.reranker else self.final_k,
        )
        if self.reranker is None:
            return fused
        return await self.reranker.rerank(query, fused, self.final_k)
