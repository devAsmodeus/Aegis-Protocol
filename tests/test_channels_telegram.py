"""Unit tests for `aegis.channels.telegram.TelegramChannel`.

We don't bring up aiogram in default CI. Tests monkeypatch
`sys.modules['aiogram']` with a fake module so the lazy import inside
the adapter resolves to a stand-in `Bot` that records calls.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest
from aegis.channels.base import OutgoingMessage
from aegis.channels.telegram import TelegramChannel


class _FakeBot:
    def __init__(self, *, token: str) -> None:
        self.token = token
        self.calls: list[dict[str, Any]] = []

    async def send_message(self, *, chat_id: int, text: str) -> None:
        self.calls.append({"chat_id": chat_id, "text": text})


def test_to_incoming_translates_aiogram_message() -> None:
    chan = TelegramChannel(bot_token="x", tenant_id="t-1")

    message = types.SimpleNamespace(
        text="hi there",
        from_user=types.SimpleNamespace(id=42),
        chat=types.SimpleNamespace(id=7),
    )

    incoming = chan.to_incoming(message)

    assert incoming.text == "hi there"
    assert incoming.external_user_id == "42"
    assert incoming.channel == "telegram"
    assert incoming.tenant_id == "t-1"
    assert incoming.conversation_external_id == "7"


def test_to_incoming_handles_missing_fields_gracefully() -> None:
    chan = TelegramChannel(bot_token="x")
    message = types.SimpleNamespace()

    incoming = chan.to_incoming(message)

    assert incoming.text == ""
    assert incoming.external_user_id == ""
    assert incoming.conversation_external_id == ""


@pytest.mark.asyncio
async def test_send_uses_lazy_aiogram_bot(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = types.ModuleType("aiogram")
    fake_module.Bot = _FakeBot  # type: ignore[attr-defined]

    class _FakeDispatcher: ...

    fake_module.Dispatcher = _FakeDispatcher  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aiogram", fake_module)

    chan = TelegramChannel(bot_token="abc-token")

    await chan.send(
        OutgoingMessage(text="reply", channel="telegram", conversation_external_id="123")
    )

    assert isinstance(chan.bot, _FakeBot)
    assert chan.bot.token == "abc-token"
    assert chan.bot.calls == [{"chat_id": 123, "text": "reply"}]


@pytest.mark.asyncio
async def test_send_skips_when_no_conversation_id() -> None:
    bot = _FakeBot(token="x")
    chan = TelegramChannel(bot_token="x", bot=bot)  # type: ignore[arg-type]

    await chan.send(OutgoingMessage(text="reply", channel="telegram"))

    assert bot.calls == []
