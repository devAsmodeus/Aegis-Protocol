"""Protocols for retriever and reranker components."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from aegis.retrieval.types import RetrievalHit, RetrievalQuery


@runtime_checkable
class Retriever(Protocol):
    """Returns up to `k` hits for `query`. Order: most relevant first."""

    async def retrieve(self, query: RetrievalQuery, k: int) -> list[RetrievalHit]: ...


@runtime_checkable
class Reranker(Protocol):
    """Reorders an existing candidate list. Length ≤ input length."""

    async def rerank(
        self,
        query: RetrievalQuery,
        hits: list[RetrievalHit],
        k: int,
    ) -> list[RetrievalHit]: ...
