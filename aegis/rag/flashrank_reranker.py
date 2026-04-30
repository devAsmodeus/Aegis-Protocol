"""FlashRank-based reranker adapter.

Cross-encoder reranking via the FlashRank library. FlashRank is an
optional dependency (extra: ``rerank``) — importing this module without
the extra installed will raise `ModuleNotFoundError` only when the
adapter is actually instantiated, so the rest of `aegis.rag` stays
import-safe in minimal deployments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from aegis.retrieval.types import RetrievalHit, RetrievalQuery

if TYPE_CHECKING:  # pragma: no cover - typing only
    from flashrank import Ranker


@dataclass(slots=True)
class FlashRankReranker:
    """Cross-encoder reranker backed by `flashrank.Ranker`.

    The underlying `Ranker` is constructed lazily on first ``rerank``
    call so that simply importing this module does not pull the
    optional dependency. Inject a pre-built `Ranker` via ``ranker=`` to
    side-step the lazy path (used in tests).

    Attributes:
        model_name: FlashRank model name (e.g.
            ``"ms-marco-MiniLM-L-12-v2"``). Ignored when ``ranker`` is
            supplied.
        ranker: Pre-built FlashRank `Ranker`. Optional; built lazily on
            first call when omitted.
    """

    model_name: str = "ms-marco-MiniLM-L-12-v2"
    ranker: Ranker | None = field(default=None)

    def _ensure_ranker(self) -> Ranker:
        if self.ranker is not None:
            return self.ranker
        from flashrank import Ranker as _Ranker  # lazy import

        self.ranker = _Ranker(model_name=self.model_name)
        return self.ranker

    async def rerank(
        self,
        query: RetrievalQuery,
        hits: list[RetrievalHit],
        k: int,
    ) -> list[RetrievalHit]:
        """Reorder ``hits`` by FlashRank cross-encoder score.

        Returns up to ``k`` hits drawn from the input list. Echoes
        ``content_hash`` and ``metadata`` so the receipt remains
        reproducible; sets ``source="flashrank"`` and ``score`` to the
        FlashRank-assigned relevance.
        """
        if not hits:
            return []

        ranker = self._ensure_ranker()
        passages: list[dict[str, Any]] = [
            {"id": idx, "text": hit.content} for idx, hit in enumerate(hits)
        ]
        from flashrank import RerankRequest

        request = RerankRequest(query=query.text, passages=passages)
        ranked: list[dict[str, Any]] = ranker.rerank(request)

        out: list[RetrievalHit] = []
        for entry in ranked[:k]:
            idx = int(entry["id"])
            base = hits[idx]
            out.append(
                RetrievalHit(
                    content=base.content,
                    content_hash=base.content_hash,
                    score=float(entry.get("score", 0.0)),
                    source="flashrank",
                    metadata=dict(base.metadata),
                )
            )
        return out
