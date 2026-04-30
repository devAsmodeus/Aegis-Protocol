"""Tests for `aegis.rag.flashrank_reranker.FlashRankReranker`.

The optional `flashrank` extra is not installed in default CI. Each
test either:

* monkeypatches the lazy import path with a fake ranker, OR
* uses `pytest.importorskip("flashrank")` to skip when the extra is
  absent.

Both paths run without docker.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest
from aegis.rag.flashrank_reranker import FlashRankReranker
from aegis.retrieval.types import RetrievalHit, RetrievalQuery, content_hash


def _hit(text: str, score: float = 0.0, source: str = "dense") -> RetrievalHit:
    return RetrievalHit(
        content=text,
        content_hash=content_hash(text),
        score=score,
        source=source,
        metadata={"orig": text},
    )


@pytest.mark.asyncio
async def test_reranker_empty_input_returns_empty() -> None:
    rr = FlashRankReranker(ranker=object())  # never used

    out = await rr.rerank(RetrievalQuery(text="x"), [], k=5)

    assert out == []


@pytest.mark.asyncio
async def test_reranker_reorders_using_injected_ranker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inject a fake `flashrank.Ranker` + `RerankRequest` so the test runs
    without the optional dependency installed."""

    class FakeRanker:
        def __init__(self, **_: Any) -> None: ...

        def rerank(self, request: Any) -> list[dict[str, Any]]:
            # reverse the input order, attach descending scores
            scored = []
            for offset, passage in enumerate(reversed(request.passages)):
                scored.append({"id": passage["id"], "score": 1.0 - 0.1 * offset})
            return scored

    class FakeRequest:
        def __init__(self, *, query: str, passages: list[dict[str, Any]]) -> None:
            self.query = query
            self.passages = passages

    fake_module = types.ModuleType("flashrank")
    fake_module.Ranker = FakeRanker  # type: ignore[attr-defined]
    fake_module.RerankRequest = FakeRequest  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "flashrank", fake_module)

    hits = [_hit("apples", 0.5), _hit("bananas", 0.4), _hit("cherries", 0.3)]
    rr = FlashRankReranker()

    out = await rr.rerank(RetrievalQuery(text="fruit"), hits, k=2)

    assert [h.content for h in out] == ["cherries", "bananas"]
    # Echoed content-hash and metadata (CLAUDE.md §3 invariant).
    assert out[0].content_hash == content_hash("cherries")
    assert out[0].metadata == {"orig": "cherries"}
    assert out[0].source == "flashrank"
    assert out[0].score == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_reranker_with_real_flashrank_if_installed() -> None:
    """Smoke test against the real library when the `rerank` extra is
    present. Skipped otherwise."""
    pytest.importorskip("flashrank")
    rr = FlashRankReranker()

    hits = [
        _hit("Bitcoin is a cryptocurrency."),
        _hit("Cats are small carnivorous mammals."),
        _hit("Ethereum is a decentralized blockchain platform."),
    ]
    out = await rr.rerank(RetrievalQuery(text="What is Ethereum?"), hits, k=1)

    assert len(out) == 1
    assert "Ethereum" in out[0].content
    assert out[0].source == "flashrank"
