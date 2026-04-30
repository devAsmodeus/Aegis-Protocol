"""In-memory channel adapter for unit tests.

Messages are injected via :meth:`InMemoryChannel.inject`; replies pile
up in :attr:`InMemoryChannel.outbox`. A single call to
:meth:`InMemoryChannel.start` drains every pending inbound message
through the supplied handler — no asyncio queues, no real I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aegis.channels.base import IncomingHandler, IncomingMessage, OutgoingMessage


@dataclass(slots=True)
class InMemoryChannel:
    """Test-only channel adapter.

    Attributes:
        channel: Channel label echoed into outbound messages. Defaults
            to ``"memory"``.
        inbox: Pending inbound messages drained on :meth:`start`.
        outbox: All outbound messages observed. Tests assert against
            this list.
    """

    channel: str = "memory"
    inbox: list[IncomingMessage] = field(default_factory=list)
    outbox: list[OutgoingMessage] = field(default_factory=list)

    def inject(
        self,
        text: str,
        *,
        external_user_id: str = "test-user",
        tenant_id: str | None = None,
        conversation_external_id: str | None = None,
    ) -> None:
        """Append a new inbound message to the queue."""
        self.inbox.append(
            IncomingMessage(
                text=text,
                external_user_id=external_user_id,
                channel=self.channel,
                tenant_id=tenant_id,
                conversation_external_id=conversation_external_id,
            )
        )

    async def send(self, message: OutgoingMessage) -> None:
        self.outbox.append(message)

    async def start(self, handler: IncomingHandler) -> None:
        pending = list(self.inbox)
        self.inbox.clear()
        for incoming in pending:
            reply = await handler(incoming)
            await self.send(reply)
