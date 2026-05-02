"""ENS forward + reverse lookups.

The :class:`EnsResolver` wraps :class:`web3.AsyncWeb3` over an
:class:`AsyncHTTPProvider` pointed at ``Settings.eth_rpc_url``.
Misses (unknown name, no reverse record) return ``None`` instead of
raising — the caller decides whether that's an error.

Tests use :class:`StubEnsResolver`, a deterministic in-memory
mapping that satisfies :class:`EnsResolverProtocol` without touching
the network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import structlog
from eth_utils.address import to_checksum_address

if TYPE_CHECKING:  # pragma: no cover - typing only
    from web3 import AsyncWeb3

_log = structlog.get_logger(__name__)


@runtime_checkable
class EnsResolverProtocol(Protocol):
    """Forward + reverse ENS lookup surface.

    Implemented by :class:`EnsResolver` (real RPC) and
    :class:`StubEnsResolver` (in-memory test fixture).
    """

    async def resolve_name(self, name: str) -> str | None:
        """Return the checksummed address for ``name``, or ``None``."""

    async def reverse_lookup(self, address: str) -> str | None:
        """Return the primary ENS name for ``address``, or ``None``."""


@dataclass(slots=True)
class EnsResolver:
    """Live ENS resolver backed by an HTTP RPC endpoint.

    Attributes:
        rpc_url: HTTPS RPC endpoint (e.g. mainnet via Alchemy/Infura).
            Sourced from :attr:`aegis.config.Settings.eth_rpc_url`.
        web3: Pre-built :class:`AsyncWeb3` instance, optional. When
            ``None`` the resolver lazily constructs one on first use so
            module import stays cheap and side-effect-free.
    """

    rpc_url: str
    web3: AsyncWeb3 | None = field(default=None)  # type: ignore[type-arg]

    def _ensure_web3(self) -> AsyncWeb3:  # type: ignore[type-arg]
        if self.web3 is not None:
            return self.web3
        from web3 import AsyncHTTPProvider  # lazy import
        from web3 import AsyncWeb3 as _AsyncWeb3  # lazy import

        self.web3 = _AsyncWeb3(AsyncHTTPProvider(self.rpc_url))
        return self.web3

    async def resolve_name(self, name: str) -> str | None:
        w3 = self._ensure_web3()
        try:
            address = await w3.ens.address(name)  # type: ignore[union-attr]
        except Exception as exc:
            _log.warning("ens.resolve_failed", name=name, error=str(exc))
            return None
        if not address:
            return None
        return to_checksum_address(address)

    async def reverse_lookup(self, address: str) -> str | None:
        w3 = self._ensure_web3()
        try:
            name = await w3.ens.name(to_checksum_address(address))  # type: ignore[union-attr]
        except Exception as exc:
            _log.warning("ens.reverse_failed", address=address, error=str(exc))
            return None
        if not name:
            return None
        return str(name)


@dataclass(slots=True)
class StubEnsResolver:
    """Deterministic in-memory ENS resolver for unit tests.

    Both directions are derived from the same ``forward`` mapping so
    tests don't have to keep two dicts in sync.
    """

    forward: dict[str, str] = field(default_factory=dict)

    def _reverse(self) -> dict[str, str]:
        return {to_checksum_address(addr): name for name, addr in self.forward.items()}

    async def resolve_name(self, name: str) -> str | None:
        addr = self.forward.get(name)
        if addr is None:
            return None
        return to_checksum_address(addr)

    async def reverse_lookup(self, address: str) -> str | None:
        try:
            checksummed = to_checksum_address(address)
        except ValueError:
            return None
        return self._reverse().get(checksummed)
