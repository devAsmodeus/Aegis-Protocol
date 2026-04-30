"""Core retrieval data types and the canonical content-hash function."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


def content_hash(text: str) -> str:
    """Return sha256 hex digest of the chunk text (UTF-8).

    Per `CLAUDE.md` §3, `Receipt.retrieval_ids` stores content-hashes — not
    Qdrant point ids — so a receipt is reproducible after a re-index.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    """Inbound query to a `Retriever`."""

    text: str
    tenant_id: str | None = None
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    """A single hit returned by a `Retriever`.

    Attributes:
        content: Raw chunk text.
        content_hash: sha256 of `content`. Must be self-consistent
            (`content_hash(hit.content) == hit.content_hash`).
        score: Source-specific score (cosine, BM25, RRF, …). Higher is better.
        source: Free-form label of the retriever that produced the hit
            (e.g. ``"dense"``, ``"bm25"``, ``"rrf"``, ``"rerank"``).
        metadata: Opaque payload echoed from the store; safe to ignore.
    """

    content: str
    content_hash: str
    score: float
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)
