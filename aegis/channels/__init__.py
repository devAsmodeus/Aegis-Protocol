"""Channel adapters: Telegram, Discord, and an in-memory test channel.

Channel adapters translate between platform-native events and the
agent's :class:`~aegis.agent.types.AgentRequest` /
:class:`~aegis.agent.types.AgentResponse` shape. They own the bot
client and run a long-lived poll/event loop; the agent runtime is
called per inbound message.
"""

from aegis.channels.base import (
    ChannelAdapter,
    IncomingHandler,
    IncomingMessage,
    OutgoingMessage,
)
from aegis.channels.memory import InMemoryChannel

__all__ = [
    "ChannelAdapter",
    "InMemoryChannel",
    "IncomingHandler",
    "IncomingMessage",
    "OutgoingMessage",
]
