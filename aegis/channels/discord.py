"""Discord channel adapter.

Built on top of `discord.py` (extra: ``discord``). The dependency is
lazy-imported so the module is import-safe in deployments that don't
need Discord. Tests inject a fake `discord` module via
``sys.modules['discord']`` and exercise the translation/send paths
directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from aegis.channels.base import IncomingHandler, IncomingMessage, OutgoingMessage

if TYPE_CHECKING:  # pragma: no cover - typing only
    from discord import Client


@dataclass(slots=True)
class DiscordChannel:
    """`discord.py`-backed channel adapter.

    Attributes:
        bot_token: Discord bot token.
        tenant_id: Logical tenant threaded into incoming messages.
        client: Optional pre-built `discord.Client`. When ``None`` a
            new one is constructed lazily with ``Intents.default()``.
    """

    bot_token: str
    tenant_id: str | None = None
    client: Client | None = field(default=None)
    channel: str = "discord"

    def _ensure_client(self) -> Client:
        if self.client is not None:
            return self.client
        import discord  # lazy import

        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        return self.client

    def to_incoming(self, message: Any) -> IncomingMessage:
        """Translate a `discord.Message` into an `IncomingMessage`.

        Pulled out as a separate method so unit tests can verify the
        translation without importing discord.py.
        """
        return IncomingMessage(
            text=str(getattr(message, "content", "") or ""),
            external_user_id=str(getattr(getattr(message, "author", None), "id", "")),
            channel=self.channel,
            tenant_id=self.tenant_id,
            conversation_external_id=str(getattr(getattr(message, "channel", None), "id", "")),
        )

    async def send(self, message: OutgoingMessage) -> None:
        """Post a reply via the lazy `Client.get_channel` lookup.

        ``conversation_external_id`` must be a stringified Discord
        channel id.
        """
        if message.conversation_external_id is None:
            return
        client = self._ensure_client()
        # Discord's get_channel returns a Union including channel kinds
        # without `.send` (e.g. CategoryChannel). Real bot deployments
        # only point conversation_external_id at messageable channels.
        target = cast(Any, client.get_channel(int(message.conversation_external_id)))
        if target is None:
            return
        await target.send(message.text)

    async def start(self, handler: IncomingHandler) -> None:
        client = self._ensure_client()

        async def _on_message(message: Any) -> None:
            if getattr(getattr(message, "author", None), "bot", False):
                return
            incoming = self.to_incoming(message)
            outgoing = await handler(incoming)
            if outgoing.conversation_external_id is None:
                return
            await message.channel.send(outgoing.text)

        client.event(_on_message)
        await client.start(self.bot_token)
