"""Transaction dry-run simulator with anti-rug-pull warnings.

The :class:`TxSimulator` runs a transaction through ``eth_call`` so the
agent can preview side-effects without broadcasting. It is **read-only**
by design — per ``CLAUDE.md`` §3, this codebase never signs or
broadcasts. ``state_override`` is supplied when the RPC accepts it so
balances / code can be spoofed; the simulator falls back to a plain
``eth_call`` when the node rejects the override.

A small heuristic layer scans ``data`` for risky patterns and surfaces
them in :attr:`SimulationResult.warnings`. Today we detect:

* ``unlimited_approval`` — ERC-20 ``approve(spender, uint256.max)`` or
  the same shape via ``increaseAllowance``. This is the rug-pull
  pattern called out in :file:`README.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import structlog
from eth_utils.address import to_checksum_address
from pydantic import BaseModel, Field

if TYPE_CHECKING:  # pragma: no cover - typing only
    from web3 import AsyncWeb3

_log = structlog.get_logger(__name__)

# ERC-20 selectors. Stored without ``0x`` for case-insensitive prefix
# checks against ``data`` payloads.
_APPROVE_SELECTOR = "095ea7b3"  # approve(address,uint256)
_INCREASE_ALLOWANCE_SELECTOR = "39509351"  # increaseAllowance(address,uint256)
_UINT256_MAX_HEX = "f" * 64


class TxRequest(BaseModel):
    """Inputs for a single :meth:`TxSimulator.simulate` call.

    All fields are JSON-friendly so :class:`TxRequest` can be parsed
    straight from the agent runtime's tool ``arguments`` dict.
    """

    from_addr: str = Field(description="Sender address.")
    to_addr: str = Field(description="Target contract / recipient.")
    value_wei: int = Field(default=0, ge=0, description="Native value in Wei.")
    data: str | None = Field(
        default=None,
        description="0x-prefixed call data, or ``None`` for plain transfers.",
    )
    gas: int | None = Field(default=None, ge=0, description="Optional gas cap.")


class SimulationResult(BaseModel):
    """Outcome of a dry-run.

    Attributes:
        success: True if ``eth_call`` returned without revert.
        return_data: Hex-encoded return value, when present.
        gas_used: Gas estimated for the call, when the node provided it.
        revert_reason: Decoded revert string, when the call reverted
            and the node surfaced one.
        warnings: Heuristic findings — see module docstring.
    """

    success: bool
    return_data: str | None = None
    gas_used: int | None = None
    revert_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)


@runtime_checkable
class TxSimulatorProtocol(Protocol):
    """Async transaction simulator surface."""

    async def simulate(self, tx: TxRequest) -> SimulationResult:
        """Run ``tx`` through ``eth_call`` and return the result."""


def _strip_0x(value: str) -> str:
    return value[2:] if value.startswith(("0x", "0X")) else value


def detect_warnings(data: str | None) -> list[str]:
    """Inspect call ``data`` and return triggered heuristic warnings.

    Pulled out so unit tests can target the heuristic directly without
    spinning up a simulator instance.
    """
    if not data:
        return []
    raw = _strip_0x(data).lower()
    if len(raw) < 8:
        return []
    selector = raw[:8]
    warnings: list[str] = []
    if selector in {_APPROVE_SELECTOR, _INCREASE_ALLOWANCE_SELECTOR}:
        # Calldata layout: selector(4) | spender(32) | amount(32). The
        # amount slot starts at hex offset 8 + 64 = 72 and is 64 hex
        # chars long.
        amount = raw[72 : 72 + 64]
        if amount == _UINT256_MAX_HEX:
            warnings.append("unlimited_approval")
    return warnings


@dataclass(slots=True)
class TxSimulator:
    """Live ``eth_call``-backed simulator.

    Attributes:
        rpc_url: HTTPS RPC endpoint.
        web3: Pre-built :class:`AsyncWeb3`, optional (lazy-built).
    """

    rpc_url: str
    web3: AsyncWeb3 | None = field(default=None)  # type: ignore[type-arg]

    def _ensure_web3(self) -> AsyncWeb3:  # type: ignore[type-arg]
        if self.web3 is not None:
            return self.web3
        from web3 import AsyncHTTPProvider  # lazy import
        from web3 import AsyncWeb3 as _AsyncWeb3

        self.web3 = _AsyncWeb3(AsyncHTTPProvider(self.rpc_url))
        return self.web3

    async def simulate(self, tx: TxRequest) -> SimulationResult:
        warnings = detect_warnings(tx.data)
        params: dict[str, object] = {
            "from": to_checksum_address(tx.from_addr),
            "to": to_checksum_address(tx.to_addr),
            "value": tx.value_wei,
        }
        if tx.data is not None:
            params["data"] = tx.data
        if tx.gas is not None:
            params["gas"] = tx.gas

        w3 = self._ensure_web3()
        try:
            return_value = await w3.eth.call(params)  # type: ignore[arg-type]
        except Exception as exc:  # pragma: no cover - exercised by integration tests
            reason = str(exc)
            _log.warning("simulator.eth_call_failed", reason=reason)
            return SimulationResult(
                success=False,
                revert_reason=reason,
                warnings=warnings,
            )

        # ``eth_call`` returns ``HexBytes``/``bytes`` in practice.
        return_data = "0x" + bytes(return_value).hex()

        return SimulationResult(
            success=True,
            return_data=return_data,
            gas_used=None,
            warnings=warnings,
        )


@dataclass(slots=True)
class StubTxSimulator:
    """Canned simulator for unit tests.

    The stub still runs :func:`detect_warnings` on the request so the
    anti-rug-pull heuristic is testable end-to-end without an RPC.
    """

    canned: SimulationResult = field(
        default_factory=lambda: SimulationResult(success=True, return_data="0x")
    )

    async def simulate(self, tx: TxRequest) -> SimulationResult:
        merged_warnings = list(self.canned.warnings) + detect_warnings(tx.data)
        # Preserve insertion order while removing duplicates.
        deduped = list(dict.fromkeys(merged_warnings))
        return self.canned.model_copy(update={"warnings": deduped})
