"""BM25 retriever backed by Qdrant sparse vectors + FastEmbed BM25.

Mirrors `QdrantDenseRetriever`: sparse vectors are pre-computed by FastEmbed's
``Qdrant/bm25`` model and queried via Qdrant's sparse-vector search. The
retriever assumes the collection already has a named sparse-vector slot
populated by the indexer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from aegis.retrieval.dense import _hit_from_point, _tenant_filter
from aegis.retrieval.types import RetrievalHit, RetrievalQuery

if TYPE_CHECKING:
    from fastembed import SparseTextEmbedding
    from qdrant_client import AsyncQdrantClient


@dataclass(slots=True)
class QdrantBM25Retriever:
    """Sparse BM25 search over a named sparse-vector slot.

    Attributes:
        client: Async Qdrant client.
        collection: Collection name.
        encoder: FastEmbed `SparseTextEmbedding` (BM25 model).
        vector_name: Named sparse-vector slot. Default ``"bm25"``.
        content_field: Payload key holding the chunk text.
    """

    client: AsyncQdrantClient
    collection: str
    encoder: SparseTextEmbedding
    vector_name: str = "bm25"
    content_field: str = "content"

    async def retrieve(self, query: RetrievalQuery, k: int) -> list[RetrievalHit]:
        from qdrant_client import models  # local import: qdrant optional at import time

        sparse = next(iter(self.encoder.embed([query.text])))
        response = await self.client.query_points(
            collection_name=self.collection,
            query=models.SparseVector(
                indices=sparse.indices.tolist(),
                values=sparse.values.tolist(),
            ),
            using=self.vector_name,
            limit=k,
            with_payload=True,
            query_filter=_tenant_filter(query.tenant_id),
        )
        return [_hit_from_point(p, self.content_field, "bm25") for p in response.points]
