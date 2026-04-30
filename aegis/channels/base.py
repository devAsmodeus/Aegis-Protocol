"""Channel adapter Protocol and shared message types.

A *channel* is anywhere a user can talk to the agent: Telegram,
Discord, an admin-panel web UI, or an in-memory test queue. All of
them adapt platform events to a single shape consumed by the agent
runtime.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class IncomingMessage:
    """Inbound user message after platform-specific normalization.

    Attributes:
        text: Raw user text.
        external_user_id: Platform-native user id (Telegram user id,
            Discord snowflake, …). Stored verbatim for receipts.
        channel: Channel label (``"telegram"``, ``"discord"``, …).
        tenant_id: Logical tenant resolved by the adapter from a bot
            token / guild id. ``None`` if the adapter doesn't know yet.
        conversation_external_id: Platform-native chat / channel id so
            replies can be routed back. May be a Telegram chat id or a
            Discord channel id, stringified.
    """

    text: str
    external_user_id: str
    channel: str
    tenant_id: str | None = None
    conversation_external_id: str | None = None


@dataclass(frozen=True, slots=True)
class OutgoingMessage:
    """Reply payload the adapter posts back to the platform."""

    text: str
    channel: str
    conversation_external_id: str | None = None


IncomingHandler = Callable[[IncomingMessage], Awaitable[OutgoingMessage]]
"""Callback signature: takes an inbound message, returns the reply."""


@runtime_checkable
class ChannelAdapter(Protocol):
    """Common interface every channel adapter implements."""

    @property
    def channel(self) -> str:
        """Channel label echoed into messages."""

    async def send(self, message: OutgoingMessage) -> None:
        """Post a single reply back to the platform."""

    async def start(self, handler: IncomingHandler) -> None:
        """Run the inbound event loop, dispatching to ``handler``.

        Adapters are free to make this blocking (real platform clients)
        or single-shot (in-memory tests).
        """
