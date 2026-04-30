"""Stubs respect `k`, compute content_hash consistently, and conform to Protocols."""

from __future__ import annotations

from aegis.retrieval import (
    IdentityReranker,
    Reranker,
    RetrievalHit,
    RetrievalQuery,
    Retriever,
    StaticRetriever,
    content_hash,
)


async def test_static_retriever_truncates_to_k() -> None:
    r = StaticRetriever(
        label="dense",
        chunks=[(f"c{i}", 1.0 - i * 0.1, {}) for i in range(5)],
    )
    hits = await r.retrieve(RetrievalQuery(text="ignored"), k=3)
    assert [h.content for h in hits] == ["c0", "c1", "c2"]
    assert all(h.source == "dense" for h in hits)


async def test_static_retriever_computes_content_hash() -> None:
    r = StaticRetriever(label="dense", chunks=[("alpha", 1.0, {})])
    hits = await r.retrieve(RetrievalQuery(text="x"), k=1)
    assert hits[0].content_hash == content_hash("alpha")


async def test_static_retriever_copies_metadata_per_hit() -> None:
    shared: dict[str, object] = {"k": "v"}
    r = StaticRetriever(label="dense", chunks=[("a", 1.0, shared), ("b", 0.5, shared)])
    hits = await r.retrieve(RetrievalQuery(text="x"), k=2)
    # Mutating one hit's metadata must not leak into siblings or the source dict.
    hits[0].metadata["mutated"] = True
    assert "mutated" not in hits[1].metadata
    assert "mutated" not in shared


def test_static_retriever_is_a_retriever() -> None:
    assert isinstance(StaticRetriever(label="x"), Retriever)


def test_identity_reranker_is_a_reranker() -> None:
    assert isinstance(IdentityReranker(), Reranker)


async def test_identity_reranker_truncates_only() -> None:
    rr = IdentityReranker()
    hits = [
        RetrievalHit(content=str(i), content_hash=content_hash(str(i)), score=0.0, source="rrf")
        for i in range(5)
    ]
    out = await rr.rerank(RetrievalQuery(text="x"), hits, k=2)
    assert out == hits[:2]
    assert out is not hits  # must be a new list
