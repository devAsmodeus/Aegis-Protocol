"""RRF math: order, dedup, k_const, limit."""

from __future__ import annotations

import pytest
from aegis.retrieval import RetrievalHit, content_hash, reciprocal_rank_fusion


def _hit(text: str, score: float, source: str) -> RetrievalHit:
    return RetrievalHit(
        content=text,
        content_hash=content_hash(text),
        score=score,
        source=source,
    )


def test_rrf_orders_by_fused_score() -> None:
    a = _hit("alpha", 0.9, "dense")
    b = _hit("bravo", 0.7, "dense")
    c = _hit("charlie", 0.5, "dense")
    fused = reciprocal_rank_fusion([[a, b, c]], k_const=60)
    assert [h.content for h in fused] == ["alpha", "bravo", "charlie"]
    assert fused[0].score == pytest.approx(1.0 / 61)
    assert fused[1].score == pytest.approx(1.0 / 62)


def test_rrf_dedupes_by_content_hash_and_sums_scores() -> None:
    same_a = _hit("alpha", 0.0, "dense")
    same_b = _hit("alpha", 0.0, "bm25")
    fused = reciprocal_rank_fusion([[same_a], [same_b]], k_const=60)
    assert len(fused) == 1
    assert fused[0].score == pytest.approx(2.0 / 61)
    assert fused[0].source == "rrf"


def test_rrf_promotes_items_appearing_in_both_lists() -> None:
    # "shared" is rank 1 in dense AND rank 1 in bm25 → fused score = 2/(60+1)
    # "dense_only" is rank 0 in dense → fused score = 1/(60+1) ≈ half of "shared"
    shared = _hit("shared", 0.5, "dense")
    shared_b = _hit("shared", 0.5, "bm25")
    dense_only = _hit("dense_only", 0.9, "dense")
    bm25_only = _hit("bm25_only", 0.9, "bm25")
    fused = reciprocal_rank_fusion([[dense_only, shared], [bm25_only, shared_b]], k_const=60)
    contents = [h.content for h in fused]
    # "shared" appears at rank 2 in both lists → score = 2/62 ≈ 0.0323
    # "dense_only"/"bm25_only" appear at rank 1 in one list → 1/61 ≈ 0.0164
    assert contents[0] == "shared"
    assert set(contents[1:]) == {"dense_only", "bm25_only"}


def test_rrf_limit_truncates() -> None:
    hits = [_hit(f"chunk-{i}", 0.0, "dense") for i in range(10)]
    fused = reciprocal_rank_fusion([hits], k_const=60, limit=3)
    assert len(fused) == 3


def test_rrf_empty_input_returns_empty() -> None:
    assert reciprocal_rank_fusion([], k_const=60) == []
    assert reciprocal_rank_fusion([[], []], k_const=60) == []


def test_rrf_preserves_first_seen_metadata() -> None:
    first = RetrievalHit(
        content="alpha",
        content_hash=content_hash("alpha"),
        score=0.0,
        source="dense",
        metadata={"from": "dense"},
    )
    second = RetrievalHit(
        content="alpha",
        content_hash=content_hash("alpha"),
        score=0.0,
        source="bm25",
        metadata={"from": "bm25"},
    )
    fused = reciprocal_rank_fusion([[first], [second]], k_const=60)
    assert fused[0].metadata == {"from": "dense"}


def test_rrf_k_const_affects_score_magnitude() -> None:
    h = _hit("alpha", 0.0, "dense")
    s10 = reciprocal_rank_fusion([[h]], k_const=10)[0].score
    s60 = reciprocal_rank_fusion([[h]], k_const=60)[0].score
    assert s10 == pytest.approx(1.0 / 11)
    assert s60 == pytest.approx(1.0 / 61)
    assert s10 > s60
