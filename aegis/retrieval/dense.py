"""Dense retriever backed by Qdrant + FastEmbed.

The encoder is FastEmbed's ``BAAI/bge-small-en-v1.5`` (384-dim) per
`CLAUDE.md` §4. The retriever does not own collection lifecycle — it
assumes the collection already exists with a named dense vector slot.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from aegis.retrieval.types import RetrievalHit, RetrievalQuery, content_hash

if TYPE_CHECKING:
    from fastembed import TextEmbedding
    from qdrant_client import AsyncQdrantClient


@dataclass(slots=True)
class QdrantDenseRetriever:
    """Dense kNN search over a named vector slot in a Qdrant collection.

    Attributes:
        client: Async Qdrant client.
        collection: Collection name.
        encoder: FastEmbed `TextEmbedding` instance. Caller-owned (heavy).
        vector_name: Named vector slot used for the dense index.
            Default ``"dense"`` matches the convention used by the indexer.
        content_field: Payload key holding the chunk text. Default ``"content"``.
    """

    client: AsyncQdrantClient
    collection: str
    encoder: TextEmbedding
    vector_name: str = "dense"
    content_field: str = "content"

    async def retrieve(self, query: RetrievalQuery, k: int) -> list[RetrievalHit]:
        vector = next(iter(self.encoder.embed([query.text]))).tolist()
        response = await self.client.query_points(
            collection_name=self.collection,
            query=vector,
            using=self.vector_name,
            limit=k,
            with_payload=True,
            query_filter=_tenant_filter(query.tenant_id),
        )
        return [_hit_from_point(p, self.content_field, "dense") for p in response.points]


def _tenant_filter(tenant_id: str | None) -> Any | None:
    """Build a Qdrant Filter restricting to a tenant, or ``None``."""
    if tenant_id is None:
        return None
    from qdrant_client import models  # local import keeps qdrant optional at import time

    return models.Filter(
        must=[
            models.FieldCondition(
                key="tenant_id",
                match=models.MatchValue(value=tenant_id),
            )
        ]
    )


def _hit_from_point(point: Any, content_field: str, source: str) -> RetrievalHit:
    payload = dict(point.payload or {})
    text = str(payload.get(content_field, ""))
    return RetrievalHit(
        content=text,
        content_hash=str(payload.get("content_hash") or content_hash(text)),
        score=float(point.score),
        source=source,
        metadata=payload,
    )
