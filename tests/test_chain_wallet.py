"""Unit tests for :mod:`aegis.chain.wallet`."""

from __future__ import annotations

from decimal import Decimal

import pytest
from aegis.chain.wallet import (
    StubWalletInspector,
    TxSummary,
    WalletInspectorProtocol,
)

_ALICE = "0x742D35Cc6634C0532925A3B844bC9e7595f0bEB7"


def test_stub_inspector_satisfies_protocol() -> None:
    inspector = StubWalletInspector()
    assert isinstance(inspector, WalletInspectorProtocol)


@pytest.mark.asyncio
async def test_balance_hit_returns_decimal() -> None:
    inspector = StubWalletInspector(balances={_ALICE: Decimal("1.5")})

    assert await inspector.balance(_ALICE) == Decimal("1.5")


@pytest.mark.asyncio
async def test_balance_miss_returns_zero() -> None:
    inspector = StubWalletInspector()

    assert await inspector.balance(_ALICE) == Decimal(0)


@pytest.mark.asyncio
async def test_tx_count_returns_nonce() -> None:
    inspector = StubWalletInspector(nonces={_ALICE: 42})

    assert await inspector.tx_count(_ALICE) == 42


@pytest.mark.asyncio
async def test_recent_txs_respects_limit() -> None:
    txs = [
        TxSummary(
            hash=f"0x{'a' * 63}{i}",
            from_addr=_ALICE,
            to_addr=_ALICE,
            value_eth=Decimal("0.1"),
            block_number=100 + i,
            timestamp=1_700_000_000 + i,
        )
        for i in range(5)
    ]
    inspector = StubWalletInspector(transactions={_ALICE: txs})

    out = await inspector.recent_txs(_ALICE, limit=3)

    assert len(out) == 3
    assert out[0].block_number == 100


@pytest.mark.asyncio
async def test_recent_txs_miss_returns_empty() -> None:
    inspector = StubWalletInspector()

    assert await inspector.recent_txs(_ALICE) == []
