"""SQLAlchemy-backed :class:`ReceiptSink`.

Records every :class:`ReceiptDraft` as a :class:`aegis.db.models.Receipt`
row. The sink owns no DB lifecycle: callers inject an
``async_sessionmaker`` and the sink opens a fresh session per write.
This keeps each receipt write atomic and avoids holding a long-lived
session across the agent's tool-loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from aegis.agent.types import ReceiptDraft
from aegis.db.models import Receipt

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass(slots=True)
class SqlReceiptSink:
    """Persists receipts via async SQLAlchemy.

    Attributes:
        session_factory: An ``async_sessionmaker`` bound to an engine.
            Tests can pass any async-callable that yields an object
            implementing ``add`` + ``commit``.
        message_id_provider: Optional callable that supplies a
            ``message_id`` for the receipt. The runtime today does not
            persist conversation/message rows itself; in production
            this hooks into a separate persistence path that returns
            the message UUID for the just-saved assistant turn.
    """

    session_factory: async_sessionmaker[AsyncSession]
    message_id_provider: object | None = None

    async def record(self, draft: ReceiptDraft) -> None:
        message_id = self._resolve_message_id(draft)
        if message_id is None:
            # No persistence path yet: silently no-op so the runtime
            # can run before message persistence lands. Logged once
            # we wire structlog through the agent module.
            return

        receipt = Receipt(
            message_id=message_id,
            input_hash=draft.input_hash,
            output_hash=draft.output_hash,
            model_id=draft.model_id,
            retrieval_ids=list(draft.retrieval_hashes),
            tools_used=list(draft.tools_used),
            payload_json=dict(draft.payload),
        )
        async with self.session_factory() as session:
            session.add(receipt)
            await session.commit()

    def _resolve_message_id(self, draft: ReceiptDraft) -> UUID | None:
        provider = self.message_id_provider
        if provider is None:
            return None
        if callable(provider):
            value = provider(draft)
            return value if isinstance(value, UUID) else None
        return None
