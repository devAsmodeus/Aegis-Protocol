"""Helpers for creating ENS subnames via :solidity:`ENSRegistry`.

The flow we support: a project that owns ``aave.eth`` wants to mint a
subname ``support.aave.eth`` and point its resolver to the agent's
wallet. This calls the canonical ENS registry's ``setSubnodeRecord``
in one tx.

Per ``CLAUDE.md`` §3, this module **never auto-signs**: when no
``signer_account`` is supplied :func:`register_subname` returns the
unsigned transaction dict for the caller to sign with a user-produced
key. The stub variant :class:`StubSubnameRegistrar` records every
invocation so unit tests can assert on call shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog
from eth_utils.address import to_checksum_address
from eth_utils.crypto import keccak

if TYPE_CHECKING:  # pragma: no cover - typing only
    from web3 import AsyncWeb3

_log = structlog.get_logger(__name__)

# Canonical ENS Registry mainnet address. The same address is used on
# Sepolia + Goerli; only chain-specific deployments differ. Callers can
# override via the ``ens_registry`` argument.
ENS_REGISTRY_MAINNET = "0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e"

# Minimal ABI surface — we only call setSubnodeRecord here. Full ABI
# is not needed because the contract is read-only for our other paths.
_ENS_REGISTRY_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "node", "type": "bytes32"},
            {"internalType": "bytes32", "name": "label", "type": "bytes32"},
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "address", "name": "resolver", "type": "address"},
            {"internalType": "uint64", "name": "ttl", "type": "uint64"},
        ],
        "name": "setSubnodeRecord",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]


def namehash(name: str) -> bytes:
    """Compute the EIP-137 namehash for a dotted ENS name.

    The empty string maps to 32 zero bytes. Each label is hashed with
    keccak256 and folded into the running node hash. Pulled out so
    unit tests can assert known vectors (e.g. ``aave.eth``).
    """
    node = bytes(32)
    if name:
        labels = name.split(".")
        for label in reversed(labels):
            label_hash = keccak(text=label)
            node = keccak(node + label_hash)
    return node


def label_hash(label: str) -> bytes:
    """keccak256 of a single ENS label (the leftmost component)."""
    return keccak(text=label)


async def register_subname(
    parent_domain: str,
    label: str,
    owner: str,
    resolver: str,
    *,
    w3: AsyncWeb3,  # type: ignore[type-arg]
    signer_account: Any | None = None,
    ens_registry: str = ENS_REGISTRY_MAINNET,
    ttl: int = 0,
) -> dict[str, Any] | str:
    """Build (and optionally broadcast) ``setSubnodeRecord``.

    Args:
        parent_domain: Domain whose owner is calling, e.g. ``"aave.eth"``.
        label: Leftmost subname component, e.g. ``"support"``.
        owner: New subname owner (typically the agent's wallet).
        resolver: ENS public resolver address for the subname.
        w3: Connected :class:`AsyncWeb3` instance.
        signer_account: Optional signer. ``None`` triggers the
            "return unsigned tx" path mandated by ``CLAUDE.md``.
        ens_registry: ENS registry address (mainnet by default).
        ttl: TTL value for the record. ``0`` is the canonical "use
            registry default" value.

    Returns:
        Unsigned tx dict (``signer_account is None``) OR
        0x-prefixed tx hash.
    """
    contract = w3.eth.contract(
        address=to_checksum_address(ens_registry),
        abi=_ENS_REGISTRY_ABI,
    )
    node = namehash(parent_domain)
    label_h = label_hash(label)
    fn = contract.functions.setSubnodeRecord(
        node,
        label_h,
        to_checksum_address(owner),
        to_checksum_address(resolver),
        ttl,
    )
    if signer_account is None:
        tx = await fn.build_transaction({"from": to_checksum_address(owner)})
        _log.info("ens_subname.unsigned", parent=parent_domain, label=label)
        return dict(tx)
    from_addr = to_checksum_address(signer_account.address)
    nonce = await w3.eth.get_transaction_count(from_addr)
    tx = await fn.build_transaction({"from": from_addr, "nonce": nonce})
    signed = signer_account.sign_transaction(tx)
    tx_hash = await w3.eth.send_raw_transaction(signed.rawTransaction)
    return "0x" + bytes(tx_hash).hex()


@dataclass(slots=True)
class StubSubnameRegistrar:
    """Records calls to :meth:`register` for unit tests.

    Mirrors the same "return unsigned tx" semantics as
    :func:`register_subname` so tests of upstream callers that branch
    on the return type can drive both code paths.
    """

    calls: list[dict[str, Any]] = field(default_factory=list)

    async def register(
        self,
        parent_domain: str,
        label: str,
        owner: str,
        resolver: str,
        *,
        signer_account: Any | None = None,
        ttl: int = 0,
    ) -> dict[str, Any] | str:
        record = {
            "parent_domain": parent_domain,
            "label": label,
            "owner": to_checksum_address(owner),
            "resolver": to_checksum_address(resolver),
            "ttl": ttl,
            "signed": signer_account is not None,
        }
        self.calls.append(record)
        if signer_account is None:
            return {
                "to": ENS_REGISTRY_MAINNET,
                "data": f"setSubnodeRecord:{parent_domain}:{label}",
                "value": 0,
            }
        return "0x" + ("cd" * 32)
