"""Telegram channel adapter.

Built on top of `aiogram` (extra: ``telegram``). The dependency is
lazy-imported inside the constructor so the module is import-safe in
deployments that only need Discord or the in-memory channel.

Tests monkeypatch ``sys.modules['aiogram']`` with a fake module that
records ``send_message`` calls — no real network, no token.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from aegis.channels.base import IncomingHandler, IncomingMessage, OutgoingMessage

if TYPE_CHECKING:  # pragma: no cover - typing only
    from aiogram import Bot, Dispatcher


@dataclass(slots=True)
class TelegramChannel:
    """AIOgram-backed Telegram adapter.

    Attributes:
        bot_token: Telegram bot token (`pydantic.SecretStr` or plain
            ``str`` from settings). Stored verbatim — never logged.
        tenant_id: Logical tenant resolved by the deployment owner;
            threaded into every :class:`IncomingMessage`.
        bot: Pre-built `aiogram.Bot`, optional. When ``None`` the
            adapter constructs one lazily on first use.
        dispatcher: Pre-built `aiogram.Dispatcher`, optional.
    """

    bot_token: str
    tenant_id: str | None = None
    bot: Bot | None = field(default=None)
    dispatcher: Dispatcher | None = field(default=None)
    channel: str = "telegram"

    def _ensure_bot(self) -> Bot:
        if self.bot is not None:
            return self.bot
        from aiogram import Bot as _Bot  # lazy import

        self.bot = _Bot(token=self.bot_token)
        return self.bot

    def _ensure_dispatcher(self) -> Dispatcher:
        if self.dispatcher is not None:
            return self.dispatcher
        from aiogram import Dispatcher as _Dispatcher  # lazy import

        self.dispatcher = _Dispatcher()
        return self.dispatcher

    def to_incoming(self, message: Any) -> IncomingMessage:
        """Translate an `aiogram.types.Message` into an `IncomingMessage`.

        Pulled out as a separate method so unit tests can exercise the
        translation without importing aiogram.
        """
        return IncomingMessage(
            text=str(getattr(message, "text", "") or ""),
            external_user_id=str(getattr(getattr(message, "from_user", None), "id", "")),
            channel=self.channel,
            tenant_id=self.tenant_id,
            conversation_external_id=str(getattr(getattr(message, "chat", None), "id", "")),
        )

    async def send(self, message: OutgoingMessage) -> None:
        if message.conversation_external_id is None:
            return
        bot = self._ensure_bot()
        await bot.send_message(
            chat_id=int(message.conversation_external_id),
            text=message.text,
        )

    async def start(self, handler: IncomingHandler) -> None:
        from aiogram.types import Message  # lazy import

        bot = self._ensure_bot()
        dp = self._ensure_dispatcher()

        async def _on_message(message: Message) -> None:
            incoming = self.to_incoming(message)
            outgoing = await handler(incoming)
            await self.send(outgoing)

        # `dp.message()` registers the handler. Cast keeps the type
        # surface consistent regardless of whether `aiogram` is
        # installed in the type-checker's environment (CI installs the
        # extra; default dev install does not).
        decorator = cast(Any, dp.message())
        decorator(_on_message)

        await dp.start_polling(bot)
