"""Deterministic in-memory stubs for unit tests.

Real Qdrant impls live in `aegis.retrieval.dense` and `aegis.retrieval.bm25`
and are exercised by integration tests. Stubs let us assert orchestration
logic (RRF, pipeline, agent loop) without docker.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from aegis.retrieval.types import RetrievalHit, RetrievalQuery, content_hash


@dataclass(slots=True)
class StaticRetriever:
    """Returns a fixed hit list (truncated to `k`), regardless of query.

    Hits are stored as ``(content, score, metadata)`` tuples to keep call sites
    terse; `content_hash` is computed on the fly so test fixtures can't drift
    out of sync with the canonical hash function.
    """

    label: str
    chunks: Sequence[tuple[str, float, dict[str, object]]] = field(default_factory=list)

    async def retrieve(self, query: RetrievalQuery, k: int) -> list[RetrievalHit]:
        del query
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


@dataclass(slots=True)
class IdentityReranker:
    """No-op reranker: returns the first `k` hits unchanged.

    Useful when wiring a pipeline that has an optional reranker slot but the
    real cross-encoder isn't available (e.g. unit tests, dev mode).
    """

    async def rerank(
        self,
        query: RetrievalQuery,
        hits: list[RetrievalHit],
        k: int,
    ) -> list[RetrievalHit]:
        del query
        return list(hits[:k])
