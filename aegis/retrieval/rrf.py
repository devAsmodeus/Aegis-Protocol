"""Reciprocal Rank Fusion.

Combines ranked lists from heterogeneous retrievers without requiring
score calibration: each item gets ``1 / (k_const + rank)`` summed across
the lists where it appears. The `k_const = 60` default is the canonical
value from Cormack, Clarke & Buettcher, "Reciprocal Rank Fusion outperforms
Condorcet and individual Rank Learning Methods" (SIGIR 2009).
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence

from aegis.retrieval.types import RetrievalHit


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[RetrievalHit]],
    *,
    k_const: int = 60,
    limit: int | None = None,
) -> list[RetrievalHit]:
    """Fuse multiple ranked lists into one.

    Hits are deduplicated by `content_hash`. The returned hit's `content` /
    `metadata` come from the **first** list that contained the chunk; the
    `source` is set to ``"rrf"`` and `score` is the fused RRF score.

    Args:
        ranked_lists: Each inner sequence is a list ordered most-relevant-first.
        k_const: RRF constant. 60 is the canonical default.
        limit: Truncate the fused list to this length. ``None`` = no truncation.

    Returns:
        A new list ordered by descending fused score.
    """
    accumulator: OrderedDict[str, RetrievalHit] = OrderedDict()
    scores: dict[str, float] = {}

    for ranked in ranked_lists:
        for rank, hit in enumerate(ranked):
            scores[hit.content_hash] = scores.get(hit.content_hash, 0.0) + 1.0 / (
                k_const + rank + 1
            )
            if hit.content_hash not in accumulator:
                accumulator[hit.content_hash] = hit

    fused = [
        RetrievalHit(
            content=accumulator[h].content,
            content_hash=h,
            score=scores[h],
            source="rrf",
            metadata=accumulator[h].metadata,
        )
        for h in accumulator
    ]
    fused.sort(key=lambda x: x.score, reverse=True)
    if limit is not None:
        fused = fused[:limit]
    return fused
