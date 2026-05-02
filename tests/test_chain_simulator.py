"""Unit tests for :mod:`aegis.chain.simulator`."""

from __future__ import annotations

import pytest
from aegis.chain.simulator import (
    SimulationResult,
    StubTxSimulator,
    TxRequest,
    TxSimulatorProtocol,
    detect_warnings,
)

_ALICE = "0x742D35Cc6634C0532925A3B844bC9e7595f0bEB7"
_USDC = "0xA0b86991c6218B36C1D19D4a2e9Eb0cE3606eB48"
_SPENDER = "0x" + "11" * 20


def _approve_calldata(spender_no_0x: str, amount_hex: str) -> str:
    """Build ``approve(spender, amount)`` calldata. ``amount_hex`` is 64 chars."""
    spender_padded = spender_no_0x.lower().rjust(64, "0")
    return "0x095ea7b3" + spender_padded + amount_hex


def test_stub_simulator_satisfies_protocol() -> None:
    sim = StubTxSimulator()
    assert isinstance(sim, TxSimulatorProtocol)


def test_detect_warnings_unlimited_approval() -> None:
    data = _approve_calldata(_SPENDER[2:], "f" * 64)

    assert detect_warnings(data) == ["unlimited_approval"]


def test_detect_warnings_bounded_approval_is_silent() -> None:
    bounded = "0" * 62 + "ff"  # tiny allowance
    data = _approve_calldata(_SPENDER[2:], bounded)

    assert detect_warnings(data) == []


def test_detect_warnings_unlimited_increase_allowance() -> None:
    increase_calldata = "0x39509351" + _SPENDER[2:].rjust(64, "0") + "f" * 64

    assert detect_warnings(increase_calldata) == ["unlimited_approval"]


def test_detect_warnings_unrelated_selector_is_silent() -> None:
    # transfer(address,uint256) — not the approval family.
    transfer_data = "0xa9059cbb" + _SPENDER[2:].rjust(64, "0") + "f" * 64

    assert detect_warnings(transfer_data) == []


def test_detect_warnings_empty_data_is_silent() -> None:
    assert detect_warnings(None) == []
    assert detect_warnings("") == []
    assert detect_warnings("0x") == []


@pytest.mark.asyncio
async def test_stub_simulator_returns_canned_success() -> None:
    canned = SimulationResult(success=True, return_data="0xdead", gas_used=21000)
    sim = StubTxSimulator(canned=canned)

    result = await sim.simulate(TxRequest(from_addr=_ALICE, to_addr=_USDC, value_wei=0, data=None))

    assert result.success is True
    assert result.return_data == "0xdead"
    assert result.gas_used == 21000
    assert result.warnings == []


@pytest.mark.asyncio
async def test_stub_simulator_appends_unlimited_approval_warning() -> None:
    sim = StubTxSimulator()

    data = _approve_calldata(_SPENDER[2:], "f" * 64)
    result = await sim.simulate(TxRequest(from_addr=_ALICE, to_addr=_USDC, data=data))

    assert result.success is True
    assert "unlimited_approval" in result.warnings


@pytest.mark.asyncio
async def test_stub_simulator_dedupes_warnings() -> None:
    canned = SimulationResult(success=True, warnings=["unlimited_approval"])
    sim = StubTxSimulator(canned=canned)

    data = _approve_calldata(_SPENDER[2:], "f" * 64)
    result = await sim.simulate(TxRequest(from_addr=_ALICE, to_addr=_USDC, data=data))

    assert result.warnings == ["unlimited_approval"]
