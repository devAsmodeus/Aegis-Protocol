"""Unit tests for :mod:`aegis.chain.ens`."""

from __future__ import annotations

import pytest
from aegis.chain.ens import EnsResolverProtocol, StubEnsResolver

_ALICE_ADDR = "0x742d35cc6634c0532925a3b844bc9e7595f0beb7"
_ALICE_CHECKSUM = "0x742D35Cc6634C0532925A3B844bC9e7595f0bEB7"


def test_stub_resolver_satisfies_protocol() -> None:
    resolver = StubEnsResolver(forward={"alice.eth": _ALICE_ADDR})
    assert isinstance(resolver, EnsResolverProtocol)


@pytest.mark.asyncio
async def test_resolve_name_hit_returns_checksum() -> None:
    resolver = StubEnsResolver(forward={"alice.eth": _ALICE_ADDR})

    addr = await resolver.resolve_name("alice.eth")

    assert addr == _ALICE_CHECKSUM


@pytest.mark.asyncio
async def test_resolve_name_miss_returns_none() -> None:
    resolver = StubEnsResolver(forward={"alice.eth": _ALICE_ADDR})

    assert await resolver.resolve_name("bob.eth") is None


@pytest.mark.asyncio
async def test_reverse_lookup_hit_returns_name() -> None:
    resolver = StubEnsResolver(forward={"alice.eth": _ALICE_ADDR})

    name = await resolver.reverse_lookup(_ALICE_ADDR)

    assert name == "alice.eth"


@pytest.mark.asyncio
async def test_reverse_lookup_miss_returns_none() -> None:
    resolver = StubEnsResolver(forward={"alice.eth": _ALICE_ADDR})

    other = "0x0000000000000000000000000000000000000001"
    assert await resolver.reverse_lookup(other) is None


@pytest.mark.asyncio
async def test_reverse_lookup_invalid_address_returns_none() -> None:
    resolver = StubEnsResolver(forward={"alice.eth": _ALICE_ADDR})

    assert await resolver.reverse_lookup("not-an-address") is None
