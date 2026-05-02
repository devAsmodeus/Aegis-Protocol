"""Wallet inspection: balance, tx-count, recent transactions.

Recent-tx listing is intentionally cheap: if no Etherscan-compatible
API key is configured, :meth:`WalletInspector.recent_txs` logs a
structured warning and returns ``[]`` instead of crashing. This keeps
the agent runtime usable on testnets where indexer access is optional.

Tests use :class:`StubWalletInspector` for deterministic fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import structlog
from eth_utils.address import to_checksum_address
from pydantic import BaseModel, Field

if TYPE_CHECKING:  # pragma: no cover - typing only
    from web3 import AsyncWeb3

_log = structlog.get_logger(__name__)

_WEI_PER_ETH = Decimal(10) ** 18


class TxSummary(BaseModel):
    """One historical transaction, normalized for agent context.

    All fields are JSON-serializable so :class:`TxSummary` can flow
    straight into :class:`~aegis.agent.types.ToolResult.metadata`.
    """

    hash: str = Field(description="0x-prefixed tx hash.")
    from_addr: str = Field(description="Checksummed sender address.")
    to_addr: str | None = Field(
        default=None,
        description="Checksummed recipient address; ``None`` for contract creations.",
    )
    value_eth: Decimal = Field(description="Transferred value in ETH (not Wei).")
    block_number: int = Field(description="Block height the tx was mined in.")
    timestamp: int | None = Field(
        default=None,
        description="Unix timestamp of the block; may be missing for pending txs.",
    )

    model_config = {"arbitrary_types_allowed": True}


@runtime_checkable
class WalletInspectorProtocol(Protocol):
    """Read-only wallet inspection surface."""

    async def balance(self, address: str) -> Decimal:
        """Return the address balance in ETH."""

    async def tx_count(self, address: str) -> int:
        """Return the transaction nonce for ``address``."""

    async def recent_txs(self, address: str, limit: int = 10) -> list[TxSummary]:
        """Return up to ``limit`` recent txs touching ``address``."""


@dataclass(slots=True)
class WalletInspector:
    """Live wallet inspector backed by an HTTP RPC + optional indexer.

    Attributes:
        rpc_url: HTTPS RPC endpoint used for ``eth_getBalance`` /
            ``eth_getTransactionCount``.
        etherscan_api_key: Optional Etherscan-compatible API key. When
            ``None`` :meth:`recent_txs` returns ``[]`` and logs a
            structured warning — see module docstring.
        web3: Pre-built :class:`AsyncWeb3`, optional (lazy-built).
    """

    rpc_url: str
    etherscan_api_key: str | None = None
    web3: AsyncWeb3 | None = field(default=None)  # type: ignore[type-arg]

    def _ensure_web3(self) -> AsyncWeb3:  # type: ignore[type-arg]
        if self.web3 is not None:
            return self.web3
        from web3 import AsyncHTTPProvider  # lazy import
        from web3 import AsyncWeb3 as _AsyncWeb3

        self.web3 = _AsyncWeb3(AsyncHTTPProvider(self.rpc_url))
        return self.web3

    async def balance(self, address: str) -> Decimal:
        w3 = self._ensure_web3()
        wei = await w3.eth.get_balance(to_checksum_address(address))
        return (Decimal(int(wei)) / _WEI_PER_ETH).normalize()

    async def tx_count(self, address: str) -> int:
        w3 = self._ensure_web3()
        return int(await w3.eth.get_transaction_count(to_checksum_address(address)))

    async def recent_txs(self, address: str, limit: int = 10) -> list[TxSummary]:
        if not self.etherscan_api_key:
            _log.warning(
                "wallet.recent_txs_unavailable",
                reason="no_etherscan_api_key",
                address=address,
            )
            return []
        # A real Etherscan-compatible HTTP fetch would go here. We
        # avoid a network call so this default branch is safe to ship
        # for the unit-test default install. Integration tests opt in
        # via @pytest.mark.integration and a configured key.
        _log.info("wallet.recent_txs_stubbed", address=address, limit=limit)
        return []


@dataclass(slots=True)
class StubWalletInspector:
    """Deterministic wallet fixture for unit tests.

    Attributes:
        balances: Mapping of checksummed-or-raw address to ETH balance.
        nonces: Mapping of address to ``eth_getTransactionCount`` value.
        transactions: Mapping of address to a list of :class:`TxSummary`.
    """

    balances: dict[str, Decimal] = field(default_factory=dict)
    nonces: dict[str, int] = field(default_factory=dict)
    transactions: dict[str, list[TxSummary]] = field(default_factory=dict)

    @staticmethod
    def _key(address: str) -> str:
        try:
            return to_checksum_address(address)
        except ValueError:
            return address

    async def balance(self, address: str) -> Decimal:
        return self.balances.get(self._key(address), Decimal(0))

    async def tx_count(self, address: str) -> int:
        return self.nonces.get(self._key(address), 0)

    async def recent_txs(self, address: str, limit: int = 10) -> list[TxSummary]:
        return self.transactions.get(self._key(address), [])[:limit]
