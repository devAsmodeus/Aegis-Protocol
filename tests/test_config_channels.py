"""Settings sanity for channel-adapter tokens."""

from __future__ import annotations

import pytest
from aegis.config import Settings


def test_telegram_and_discord_tokens_default_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)

    s = Settings(_env_file=None)  # type: ignore[call-arg]

    assert s.telegram_bot_token is None
    assert s.discord_bot_token is None


def test_channel_tokens_picked_up_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tg-123")
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "ds-456")

    s = Settings(_env_file=None)  # type: ignore[call-arg]

    assert s.telegram_bot_token == "tg-123"
    assert s.discord_bot_token == "ds-456"
