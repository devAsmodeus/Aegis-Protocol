"""Unit tests for :class:`aegis.chain.registry.StubAegisRegistry`.

The stub mirrors the contract's owner-only enforcement so we can
exercise business rules (register dedup, owner-only updates, unsigned
tx shape) without touching solc or an EVM. Live-network tests live
behind ``@pytest.mark.integration``.
"""

from __future__ import annotations

import pytest
from aegis.chain.registry import (
    AegisRegistryProtocol,
    AgentRecord,
    StubAegisRegistry,
    _normalize_kb_hash,
)

_OWNER_A = "0x000000000000000000000000000000000000aaaa"
_OWNER_B = "0x000000000000000000000000000000000000bbbb"
_KB_HEX = "0x" + "ab" * 32
_KB_HEX_2 = "0x" + "cd" * 32


class _FakeAccount:
    def __init__(self, address: str) -> None:
        self.address = address


def test_stub_satisfies_protocol() -> None:
    registry = StubAegisRegistry()
    assert isinstance(registry, AegisRegistryProtocol)


def test_normalize_kb_hash_accepts_bytes_and_hex() -> None:
    raw = bytes.fromhex("ab" * 32)
    assert _normalize_kb_hash(raw) == raw
    assert _normalize_kb_hash("0x" + "ab" * 32) == raw
    assert _normalize_kb_hash("ab" * 32) == raw


def test_normalize_kb_hash_rejects_wrong_length() -> None:
    with pytest.raises(ValueError):
        _normalize_kb_hash("0xdeadbeef")


def test_normalize_kb_hash_rejects_wrong_type() -> None:
    with pytest.raises(TypeError):
        _normalize_kb_hash(12345)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_register_then_get_round_trip() -> None:
    registry = StubAegisRegistry(default_owner=_OWNER_A)
    await registry.register("support.aegis.eth", _KB_HEX)

    record = await registry.get("support.aegis.eth")
    assert record is not None
    assert isinstance(record, AgentRecord)
    assert record.ens_subname == "support.aegis.eth"
    assert record.kb_cid_hash == _KB_HEX
    assert record.active is True


@pytest.mark.asyncio
async def test_get_missing_returns_none() -> None:
    registry = StubAegisRegistry()
    assert await registry.get("never-registered.eth") is None


@pytest.mark.asyncio
async def test_is_active_tracks_state() -> None:
    registry = StubAegisRegistry(default_owner=_OWNER_A)
    assert await registry.is_active("support.aegis.eth") is False

    await registry.register("support.aegis.eth", _KB_HEX)
    assert await registry.is_active("support.aegis.eth") is True

    await registry.deactivate("support.aegis.eth", caller=_OWNER_A)
    assert await registry.is_active("support.aegis.eth") is False


@pytest.mark.asyncio
async def test_register_rejects_duplicate_active_name() -> None:
    registry = StubAegisRegistry(default_owner=_OWNER_A)
    await registry.register("support.aegis.eth", _KB_HEX)

    with pytest.raises(ValueError, match="AlreadyRegistered"):
        await registry.register("support.aegis.eth", _KB_HEX_2)


@pytest.mark.asyncio
async def test_register_allowed_after_deactivate() -> None:
    registry = StubAegisRegistry(default_owner=_OWNER_A)
    await registry.register("support.aegis.eth", _KB_HEX)
    await registry.deactivate("support.aegis.eth", caller=_OWNER_A)

    await registry.register("support.aegis.eth", _KB_HEX_2)
    record = await registry.get("support.aegis.eth")
    assert record is not None
    assert record.active is True
    assert record.kb_cid_hash == _KB_HEX_2


@pytest.mark.asyncio
async def test_deactivate_owner_only() -> None:
    registry = StubAegisRegistry(default_owner=_OWNER_A)
    await registry.register("support.aegis.eth", _KB_HEX)

    with pytest.raises(ValueError, match="NotOwner"):
        await registry.deactivate("support.aegis.eth", caller=_OWNER_B)

    await registry.deactivate("support.aegis.eth", caller=_OWNER_A)
    assert await registry.is_active("support.aegis.eth") is False


@pytest.mark.asyncio
async def test_update_kb_owner_only_and_persists() -> None:
    registry = StubAegisRegistry(default_owner=_OWNER_A)
    await registry.register("support.aegis.eth", _KB_HEX)

    with pytest.raises(ValueError, match="NotOwner"):
        await registry.update_kb("support.aegis.eth", _KB_HEX_2, caller=_OWNER_B)

    await registry.update_kb("support.aegis.eth", _KB_HEX_2, caller=_OWNER_A)
    record = await registry.get("support.aegis.eth")
    assert record is not None
    assert record.kb_cid_hash == _KB_HEX_2


@pytest.mark.asyncio
async def test_register_without_signer_returns_unsigned_tx_dict() -> None:
    registry = StubAegisRegistry()
    result = await registry.register("support.aegis.eth", _KB_HEX)

    assert isinstance(result, dict)
    assert "to" in result
    assert "data" in result
    assert "value" in result


@pytest.mark.asyncio
async def test_register_with_signer_returns_tx_hash() -> None:
    registry = StubAegisRegistry()
    account = _FakeAccount(_OWNER_A)

    result = await registry.register(
        "support.aegis.eth",
        _KB_HEX,
        signer_account=account,
    )

    assert isinstance(result, str)
    assert result.startswith("0x")
    assert len(result) == 66  # 0x + 64 hex chars


@pytest.mark.asyncio
async def test_register_with_signer_records_owner() -> None:
    registry = StubAegisRegistry()
    account = _FakeAccount(_OWNER_B)

    await registry.register(
        "support.aegis.eth",
        _KB_HEX,
        signer_account=account,
    )

    record = await registry.get("support.aegis.eth")
    assert record is not None
    assert record.owner.lower() == _OWNER_B.lower()
