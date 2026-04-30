"""Tenant-scoped RAG search service.

`RagService` is the public surface every agent tool calls. It owns a
`HybridPipeline` and adds two responsibilities the pipeline doesn't
have:

1. **Tenant scoping.** Callers pass `tenant_id` as a keyword; the
   service threads it into the `RetrievalQuery`. Underlying retrievers
   apply that as a Qdrant filter (or ignore it, in stubs).
2. **Top-k override.** The pipeline returns its configured ``final_k``
   hits. The service lets callers ask for fewer with ``k=...`` without
   reconfiguring the whole pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aegis.retrieval.pipeline import HybridPipeline
from aegis.retrieval.types import RetrievalHit, RetrievalQuery


@dataclass(slots=True)
class RagService:
    """Tenant-scoped RAG search.

    Attributes:
        pipeline: The underlying hybrid retrieval pipeline. Held by
            reference so tests can swap in stub retrievers.
    """

    pipeline: HybridPipeline

    async def search(
        self,
        *,
        text: str,
        tenant_id: str | None = None,
        filters: dict[str, Any] | None = None,
        k: int | None = None,
    ) -> list[RetrievalHit]:
        """Run a query through the hybrid pipeline.

        Args:
            text: Natural-language query.
            tenant_id: Logical tenant. Threaded into `RetrievalQuery` so
                downstream Qdrant adapters can apply it as a filter.
            filters: Extra structured filters echoed into the query.
            k: Optional cap on returned hits. ``None`` means "use the
                pipeline's configured ``final_k``".
        """
        query = RetrievalQuery(
            text=text,
            tenant_id=tenant_id,
            filters=dict(filters) if filters else {},
        )
        hits = await self.pipeline.retrieve(query)
        if k is not None:
            return hits[:k]
        return hits
