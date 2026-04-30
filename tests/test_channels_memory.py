"""Unit tests for `aegis.channels.memory.InMemoryChannel`."""

from __future__ import annotations

import pytest
from aegis.channels.base import IncomingMessage, OutgoingMessage
from aegis.channels.memory import InMemoryChannel


@pytest.mark.asyncio
async def test_in_memory_channel_drains_inbox_through_handler() -> None:
    chan = InMemoryChannel()
    chan.inject("hello", external_user_id="alice")
    chan.inject("world", external_user_id="bob")

    seen: list[IncomingMessage] = []

    async def handler(msg: IncomingMessage) -> OutgoingMessage:
        seen.append(msg)
        return OutgoingMessage(
            text=f"reply: {msg.text}",
            channel=msg.channel,
            conversation_external_id=msg.conversation_external_id,
        )

    await chan.start(handler)

    assert [m.text for m in seen] == ["hello", "world"]
    assert chan.inbox == []
    assert [o.text for o in chan.outbox] == ["reply: hello", "reply: world"]
    assert all(o.channel == "memory" for o in chan.outbox)


@pytest.mark.asyncio
async def test_send_appends_to_outbox() -> None:
    chan = InMemoryChannel()
    msg = OutgoingMessage(text="x", channel="memory")

    await chan.send(msg)

    assert chan.outbox == [msg]


@pytest.mark.asyncio
async def test_start_with_empty_inbox_is_noop() -> None:
    chan = InMemoryChannel()

    async def handler(_: IncomingMessage) -> OutgoingMessage:
        raise AssertionError("handler should not be called")

    await chan.start(handler)

    assert chan.outbox == []


def test_inject_propagates_tenant_and_conversation_id() -> None:
    chan = InMemoryChannel()

    chan.inject(
        "x",
        external_user_id="u1",
        tenant_id="tenant-1",
        conversation_external_id="conv-7",
    )

    assert chan.inbox[0].tenant_id == "tenant-1"
    assert chan.inbox[0].conversation_external_id == "conv-7"
