"""Unit tests for :mod:`aegis.chain.ens_subname`.

The stub registrar is enough to exercise the ``signer_account is None``
vs ``signer_account is not None`` branches mandated by ``CLAUDE.md`` §3
("never auto-sign"). Live :func:`register_subname` calls live behind
``@pytest.mark.integration`` (none here yet).
"""

from __future__ import annotations

import pytest
from aegis.chain.ens_subname import (
    ENS_REGISTRY_MAINNET,
    StubSubnameRegistrar,
    label_hash,
    namehash,
)

_PARENT = "aegis.eth"
_LABEL = "support"
_OWNER = "0x000000000000000000000000000000000000aaaa"
_RESOLVER = "0x000000000000000000000000000000000000bbbb"


class _FakeAccount:
    def __init__(self, address: str) -> None:
        self.address = address


def test_namehash_empty_string_is_zero() -> None:
    assert namehash("") == bytes(32)


def test_namehash_eth_known_vector() -> None:
    # Known EIP-137 test vector: keccak256(0x..0 || keccak256("eth")).
    h = namehash("eth")
    assert h.hex() == "93cdeb708b7545dc668eb9280176169d1c33cfd8ed6f04690a0bcc88a93fc4ae"


def test_namehash_handles_subname() -> None:
    parent = namehash(_PARENT)
    child = namehash(f"{_LABEL}.{_PARENT}")
    assert parent != child
    assert len(child) == 32


def test_label_hash_stable() -> None:
    h1 = label_hash(_LABEL)
    h2 = label_hash(_LABEL)
    assert h1 == h2
    assert len(h1) == 32


@pytest.mark.asyncio
async def test_stub_registrar_records_unsigned_call() -> None:
    registrar = StubSubnameRegistrar()

    result = await registrar.register(
        parent_domain=_PARENT,
        label=_LABEL,
        owner=_OWNER,
        resolver=_RESOLVER,
    )

    assert isinstance(result, dict)
    assert result["to"] == ENS_REGISTRY_MAINNET
    assert _PARENT in result["data"]
    assert _LABEL in result["data"]

    assert len(registrar.calls) == 1
    call = registrar.calls[0]
    assert call["parent_domain"] == _PARENT
    assert call["label"] == _LABEL
    assert call["signed"] is False
    # Addresses come back checksummed.
    assert call["owner"].startswith("0x")
    assert call["resolver"].startswith("0x")


@pytest.mark.asyncio
async def test_stub_registrar_with_signer_returns_tx_hash() -> None:
    registrar = StubSubnameRegistrar()
    account = _FakeAccount(_OWNER)

    result = await registrar.register(
        parent_domain=_PARENT,
        label=_LABEL,
        owner=_OWNER,
        resolver=_RESOLVER,
        signer_account=account,
    )

    assert isinstance(result, str)
    assert result.startswith("0x")
    assert len(result) == 66

    assert registrar.calls[-1]["signed"] is True


@pytest.mark.asyncio
async def test_stub_registrar_records_each_call() -> None:
    registrar = StubSubnameRegistrar()
    await registrar.register(
        parent_domain=_PARENT,
        label="alpha",
        owner=_OWNER,
        resolver=_RESOLVER,
    )
    await registrar.register(
        parent_domain=_PARENT,
        label="beta",
        owner=_OWNER,
        resolver=_RESOLVER,
        ttl=60,
    )

    assert len(registrar.calls) == 2
    assert registrar.calls[0]["label"] == "alpha"
    assert registrar.calls[1]["label"] == "beta"
    assert registrar.calls[1]["ttl"] == 60
