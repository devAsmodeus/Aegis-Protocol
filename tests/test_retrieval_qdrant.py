"""End-to-end retrieval against a live Qdrant.

Marked `integration`: requires a running Qdrant at `QDRANT_URL` (or default
``http://localhost:6333`` from `aegis.config.get_settings`). The test creates
an ephemeral collection, indexes a handful of docs with both a dense vector
(BAAI/bge-small-en-v1.5) and a BM25 sparse vector, runs both retrievers,
fuses with RRF, and asserts that a query targeted at a specific chunk
surfaces it at rank 1.
"""

from __future__ import annotations

import uuid

import pytest
from aegis.retrieval import RetrievalQuery
from aegis.retrieval.pipeline import HybridPipeline

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def collection_name() -> str:
    return f"aegis-test-{uuid.uuid4().hex[:8]}"


async def test_hybrid_retrieval_against_real_qdrant(collection_name: str) -> None:
    from aegis.config import get_settings
    from aegis.retrieval.bm25 import QdrantBM25Retriever
    from aegis.retrieval.dense import QdrantDenseRetriever
    from aegis.retrieval.types import content_hash
    from fastembed import SparseTextEmbedding, TextEmbedding
    from qdrant_client import AsyncQdrantClient, models

    settings = get_settings()
    qdrant_url = settings.qdrant_url or "http://localhost:6333"
    client = AsyncQdrantClient(url=qdrant_url, api_key=settings.qdrant_api_key)
    dense_encoder = TextEmbedding("BAAI/bge-small-en-v1.5")
    bm25_encoder = SparseTextEmbedding("Qdrant/bm25")

    dense_dim = 384
    docs = [
        "Aegis Protocol is an autonomous AI support agent for Web3 communities.",
        "ENS provides decentralized human-readable names for Ethereum addresses.",
        "Reciprocal Rank Fusion combines ranked lists without score calibration.",
        "Qdrant is a vector database written in Rust.",
        "0G offers decentralized compute, storage, and data availability.",
    ]
    payloads = [{"content": d, "content_hash": content_hash(d)} for d in docs]
    dense_vecs = [v.tolist() for v in dense_encoder.embed(docs)]
    sparse_vecs = list(bm25_encoder.embed(docs))

    try:
        await client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": models.VectorParams(size=dense_dim, distance=models.Distance.COSINE),
            },
            sparse_vectors_config={"bm25": models.SparseVectorParams()},
        )
        await client.upload_points(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=i,
                    vector={
                        "dense": dense_vecs[i],
                        "bm25": models.SparseVector(
                            indices=sparse_vecs[i].indices.tolist(),
                            values=sparse_vecs[i].values.tolist(),
                        ),
                    },
                    payload=payloads[i],
                )
                for i in range(len(docs))
            ],
            wait=True,
        )

        pipeline = HybridPipeline(
            retrievers=[
                QdrantDenseRetriever(
                    client=client, collection=collection_name, encoder=dense_encoder
                ),
                QdrantBM25Retriever(
                    client=client, collection=collection_name, encoder=bm25_encoder
                ),
            ],
            fanout_k=5,
            final_k=3,
        )
        hits = await pipeline.retrieve(RetrievalQuery(text="What is ENS?"))
        assert hits
        assert "ENS" in hits[0].content
        assert hits[0].content_hash == content_hash(hits[0].content)
    finally:
        await client.delete_collection(collection_name=collection_name)
        await client.close()
