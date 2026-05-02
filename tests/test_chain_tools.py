"""Unit tests for the agent-runtime tool wrappers in :mod:`aegis.chain.tools`."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from aegis.agent.protocol import Tool
from aegis.chain.ens import StubEnsResolver
from aegis.chain.simulator import SimulationResult, StubTxSimulator
from aegis.chain.tools import InspectWalletTool, ResolveEnsTool, SimulateTxTool
from aegis.chain.wallet import StubWalletInspector, TxSummary

_ALICE_ADDR = "0x742d35cc6634c0532925a3b844bc9e7595f0beb7"
_ALICE_CHECKSUM = "0x742D35Cc6634C0532925A3B844bC9e7595f0bEB7"
_USDC = "0xA0b86991c6218B36C1D19D4a2e9Eb0cE3606eB48"


def test_chain_tools_satisfy_tool_protocol() -> None:
    resolve = ResolveEnsTool(resolver=StubEnsResolver())
    inspect = InspectWalletTool(inspector=StubWalletInspector())
    simulate = SimulateTxTool(simulator=StubTxSimulator())

    for tool in (resolve, inspect, simulate):
        assert isinstance(tool, Tool)
        # Each tool must expose a JSON-schema describing its arguments.
        assert tool.json_schema["type"] == "object"


def test_chain_tools_have_distinct_stable_names() -> None:
    names = {
        ResolveEnsTool(resolver=StubEnsResolver()).name,
        InspectWalletTool(inspector=StubWalletInspector()).name,
        SimulateTxTool(simulator=StubTxSimulator()).name,
    }
    assert names == {"resolve_ens", "inspect_wallet", "simulate_tx"}


@pytest.mark.asyncio
async def test_resolve_ens_tool_returns_json_dict() -> None:
    tool = ResolveEnsTool(resolver=StubEnsResolver(forward={"alice.eth": _ALICE_ADDR}))

    result = await tool.call({"name": "alice.eth"})

    payload = json.loads(result.output)
    assert payload == {"name": "alice.eth", "address": _ALICE_CHECKSUM}
    assert result.metadata == payload


@pytest.mark.asyncio
async def test_resolve_ens_tool_reverse_branch() -> None:
    tool = ResolveEnsTool(resolver=StubEnsResolver(forward={"alice.eth": _ALICE_ADDR}))

    result = await tool.call({"address": _ALICE_ADDR})

    payload = json.loads(result.output)
    assert payload == {"name": "alice.eth", "address": _ALICE_ADDR}


@pytest.mark.asyncio
async def test_inspect_wallet_tool_returns_balance_and_nonce() -> None:
    inspector = StubWalletInspector(
        balances={_ALICE_CHECKSUM: Decimal("2.25")},
        nonces={_ALICE_CHECKSUM: 7},
        transactions={
            _ALICE_CHECKSUM: [
                TxSummary(
                    hash="0x" + "ab" * 32,
                    from_addr=_ALICE_CHECKSUM,
                    to_addr=_USDC,
                    value_eth=Decimal("0.5"),
                    block_number=18_000_000,
                    timestamp=1_700_000_000,
                )
            ]
        },
    )
    tool = InspectWalletTool(inspector=inspector)

    result = await tool.call({"address": _ALICE_CHECKSUM})

    payload = json.loads(result.output)
    assert payload["balance_eth"] == "2.25"
    assert payload["tx_count"] == 7
    assert len(payload["recent_txs"]) == 1
    assert payload["recent_txs"][0]["block_number"] == 18_000_000
    # Decimal serialization is JSON-safe.
    json.dumps(result.metadata)


@pytest.mark.asyncio
async def test_simulate_tx_tool_surfaces_unlimited_approval_warning() -> None:
    sim = StubTxSimulator(canned=SimulationResult(success=True, return_data="0x", gas_used=23_000))
    tool = SimulateTxTool(simulator=sim)

    spender = "11" * 20
    data = "0x095ea7b3" + spender.rjust(64, "0") + "f" * 64
    result = await tool.call(
        {
            "from_addr": _ALICE_CHECKSUM,
            "to_addr": _USDC,
            "value_wei": 0,
            "data": data,
        }
    )

    payload = json.loads(result.output)
    assert payload["success"] is True
    assert "unlimited_approval" in payload["warnings"]
    assert result.metadata["warnings"] == payload["warnings"]
