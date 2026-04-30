"""Unit tests for `aegis.channels.discord.DiscordChannel`."""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest
from aegis.channels.base import OutgoingMessage
from aegis.channels.discord import DiscordChannel


class _FakeChannel:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, text: str) -> None:
        self.sent.append(text)


class _FakeClient:
    def __init__(self, *, intents: Any = None) -> None:
        self.intents = intents
        self._channels: dict[int, _FakeChannel] = {}

    def register_channel(self, cid: int) -> _FakeChannel:
        ch = _FakeChannel()
        self._channels[cid] = ch
        return ch

    def get_channel(self, cid: int) -> _FakeChannel | None:
        return self._channels.get(cid)


def _install_fake_discord(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = types.ModuleType("discord")

    class _FakeIntents:
        @classmethod
        def default(cls) -> _FakeIntents:
            inst = cls()
            return inst

        def __init__(self) -> None:
            self.message_content = False

    fake_module.Intents = _FakeIntents  # type: ignore[attr-defined]
    fake_module.Client = _FakeClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "discord", fake_module)


def test_to_incoming_translates_discord_message() -> None:
    chan = DiscordChannel(bot_token="t", tenant_id="t-1")
    message = types.SimpleNamespace(
        content="hello bot",
        author=types.SimpleNamespace(id=99, bot=False),
        channel=types.SimpleNamespace(id=555),
    )

    incoming = chan.to_incoming(message)

    assert incoming.text == "hello bot"
    assert incoming.external_user_id == "99"
    assert incoming.channel == "discord"
    assert incoming.tenant_id == "t-1"
    assert incoming.conversation_external_id == "555"


def test_to_incoming_handles_missing_fields() -> None:
    chan = DiscordChannel(bot_token="t")
    incoming = chan.to_incoming(types.SimpleNamespace())

    assert incoming.text == ""
    assert incoming.external_user_id == ""
    assert incoming.conversation_external_id == ""


@pytest.mark.asyncio
async def test_send_routes_to_get_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_discord(monkeypatch)
    chan = DiscordChannel(bot_token="t")
    client = chan._ensure_client()
    fake = client.register_channel(7)  # type: ignore[attr-defined]

    await chan.send(OutgoingMessage(text="reply", channel="discord", conversation_external_id="7"))

    assert fake.sent == ["reply"]


@pytest.mark.asyncio
async def test_send_skips_when_channel_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_discord(monkeypatch)
    chan = DiscordChannel(bot_token="t")
    chan._ensure_client()  # client has no channels registered

    await chan.send(OutgoingMessage(text="x", channel="discord", conversation_external_id="999"))

    # nothing to assert beyond "did not raise"


@pytest.mark.asyncio
async def test_send_skips_when_no_conversation_id() -> None:
    chan = DiscordChannel(bot_token="t", client=_FakeClient())  # type: ignore[arg-type]

    await chan.send(OutgoingMessage(text="x", channel="discord"))


def test_ensure_client_enables_message_content_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_discord(monkeypatch)
    chan = DiscordChannel(bot_token="t")

    client = chan._ensure_client()

    assert client.intents.message_content is True  # type: ignore[attr-defined]
