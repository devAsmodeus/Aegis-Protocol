"""Retrieval subsystem.

Hybrid search over a Qdrant-backed corpus: dense (`BAAI/bge-small-en-v1.5`)
and sparse (BM25) candidates are fused with Reciprocal Rank Fusion. Designed
around small `Protocol`s so unit tests can swap in deterministic stubs and
e2e tests use the real Qdrant impls.

`content_hash` is the canonical identifier in `RetrievalHit`: per `CLAUDE.md`
§3, `Receipt.retrieval_ids` stores content-hashes (sha256 of chunk text), not
Qdrant point ids — this keeps the receipt reproducible if the vector store
is rebuilt.
"""

from __future__ import annotations

from aegis.retrieval.protocol import Reranker, Retriever
from aegis.retrieval.rrf import reciprocal_rank_fusion
from aegis.retrieval.stubs import IdentityReranker, StaticRetriever
from aegis.retrieval.types import RetrievalHit, RetrievalQuery, content_hash

__all__ = [
    "IdentityReranker",
    "Reranker",
    "RetrievalHit",
    "RetrievalQuery",
    "Retriever",
    "StaticRetriever",
    "content_hash",
    "reciprocal_rank_fusion",
]
