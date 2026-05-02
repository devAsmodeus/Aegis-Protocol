"""Python client for :file:`contracts/AegisRegistry.sol`.

This module exposes an async client that mirrors the on-chain
contract surface — :meth:`register`, :meth:`get`, :meth:`is_active`
— plus a stub for unit tests.

Per ``CLAUDE.md`` §3 ("never sign or broadcast on-chain transactions
automatically"), :meth:`AegisRegistry.register` does **not** auto-sign
when ``signer_account`` is ``None``: it returns the unsigned tx dict
and the caller is responsible for signing externally with a
user-produced key. When a signer account is supplied (testnet only,
typically loaded from :class:`aegis.config.Settings.zerog_private_key`)
the client signs locally and broadcasts — convenience for the
deploy/register helper script, never used in production paths.

A small loader, :func:`load_deployment`, reads the JSON written by
:mod:`contracts.scripts.deploy_registry` so callers can construct a
real client from a single chain id without hard-coding addresses.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import structlog
from eth_utils.address import to_checksum_address
from pydantic import BaseModel, Field

if TYPE_CHECKING:  # pragma: no cover - typing only
    from web3 import AsyncWeb3

_log = structlog.get_logger(__name__)


class AgentRecord(BaseModel):
    """Pydantic mirror of the Solidity ``AgentRecord`` struct.

    Field names use snake_case; the on-chain struct uses camelCase but
    Python callers should never need to see the raw layout.
    """

    owner: str = Field(description="Checksummed wallet address of the project.")
    ens_subname: str = Field(description="Full subname, e.g. 'support.aave.eth'.")
    kb_cid_hash: str = Field(description="0x-prefixed sha256 of the 0G Storage CID for the KB.")
    registered_at: datetime = Field(
        description="UTC timestamp parsed from the on-chain ``registeredAt``."
    )
    active: bool = Field(description="False iff the owner has called ``deactivate``.")


@runtime_checkable
class AegisRegistryProtocol(Protocol):
    """Async surface implemented by both real + stub registries."""

    async def register(
        self,
        ens_subname: str,
        kb_cid_hash: bytes,
        *,
        signer_account: Any | None = None,
    ) -> Any:
        """Register a new agent. See :class:`AegisRegistry` for semantics."""

    async def get(self, ens_subname: str) -> AgentRecord | None:
        """Return the record for ``ens_subname`` or ``None`` if missing."""

    async def is_active(self, ens_subname: str) -> bool:
        """Return True iff a record exists AND is active."""


def _normalize_kb_hash(kb_cid_hash: bytes | str) -> bytes:
    """Coerce ``kb_cid_hash`` to a 32-byte ``bytes``.

    Accepts ``bytes`` (must be 32 bytes) or a hex string (with or
    without the ``0x`` prefix). Anything else is rejected — the
    contract slot is fixed-size.
    """
    if isinstance(kb_cid_hash, bytes):
        raw = kb_cid_hash
    elif isinstance(kb_cid_hash, str):
        stripped = kb_cid_hash[2:] if kb_cid_hash.startswith(("0x", "0X")) else kb_cid_hash
        raw = bytes.fromhex(stripped)
    else:
        raise TypeError(f"kb_cid_hash must be bytes or hex str, got {type(kb_cid_hash).__name__}")
    if len(raw) != 32:
        raise ValueError(f"kb_cid_hash must be 32 bytes, got {len(raw)}")
    return raw


def _record_from_tuple(raw: tuple[Any, ...] | list[Any]) -> AgentRecord | None:
    """Decode a Solidity-returned tuple into :class:`AgentRecord`.

    Returns ``None`` for the zero-struct (no owner set) so callers can
    distinguish "never registered" without exception handling.
    """
    owner, ens_subname, kb_cid_hash, registered_at, active = raw
    if int(owner, 16) == 0:
        return None
    return AgentRecord(
        owner=to_checksum_address(owner),
        ens_subname=ens_subname,
        kb_cid_hash="0x" + bytes(kb_cid_hash).hex(),
        registered_at=datetime.fromtimestamp(int(registered_at), tz=UTC),
        active=bool(active),
    )


@dataclass(slots=True)
class AegisRegistry:
    """Live :file:`AegisRegistry.sol` client over :class:`AsyncWeb3`.

    Attributes:
        address: Deployed contract address (checksummed).
        w3: Pre-built :class:`AsyncWeb3` instance.
        abi: Contract ABI loaded from the deployment JSON.
    """

    address: str
    w3: AsyncWeb3  # type: ignore[type-arg]
    abi: list[dict[str, Any]]

    def _contract(self) -> Any:
        return self.w3.eth.contract(address=to_checksum_address(self.address), abi=self.abi)

    async def register(
        self,
        ens_subname: str,
        kb_cid_hash: bytes | str,
        *,
        signer_account: Any | None = None,
    ) -> dict[str, Any] | str:
        """Register an agent on-chain.

        Behavior depends on ``signer_account``:

        * ``signer_account is None`` — return the **unsigned** tx dict.
          Per ``CLAUDE.md`` §3, the caller must sign and broadcast
          externally. This is the production path: agent code never
          owns user keys.
        * ``signer_account`` provided — the call is signed locally and
          broadcast; the function returns the 0x-prefixed tx hash.
          Used by the deploy/register helper script in
          development only.

        Args:
            ens_subname: Full subname, e.g. ``"support.aave.eth"``.
            kb_cid_hash: sha256 of the 0G Storage CID, as ``bytes`` or
                hex ``str``.
            signer_account: Optional :class:`eth_account.Account`
                instance (or anything with ``.key`` / ``.address``).

        Returns:
            Unsigned tx dict OR 0x-prefixed tx hash, depending on
            ``signer_account``.
        """
        kb_bytes = _normalize_kb_hash(kb_cid_hash)
        contract = self._contract()
        fn = contract.functions.register(ens_subname, kb_bytes)
        if signer_account is None:
            tx = await fn.build_transaction({"from": to_checksum_address(self.address)})
            _log.info("registry.register_unsigned", ens_subname=ens_subname)
            return dict(tx)
        from_addr = to_checksum_address(signer_account.address)
        nonce = await self.w3.eth.get_transaction_count(from_addr)
        tx = await fn.build_transaction({"from": from_addr, "nonce": nonce})
        signed = signer_account.sign_transaction(tx)
        tx_hash = await self.w3.eth.send_raw_transaction(signed.rawTransaction)
        return "0x" + bytes(tx_hash).hex()

    async def get(self, ens_subname: str) -> AgentRecord | None:
        contract = self._contract()
        raw = await contract.functions.get(ens_subname).call()
        return _record_from_tuple(raw)

    async def is_active(self, ens_subname: str) -> bool:
        contract = self._contract()
        return bool(await contract.functions.isActive(ens_subname).call())


@dataclass(slots=True)
class _StubRecord:
    owner: str
    ens_subname: str
    kb_cid_hash: bytes
    registered_at: datetime
    active: bool


@dataclass(slots=True)
class StubAegisRegistry:
    """In-memory registry for unit tests.

    Mirrors the contract's owner-only enforcement so tests verify
    business rules without needing a real EVM. ``_records`` is keyed
    by ``ens_subname`` (no keccak hashing — same semantics, simpler
    debugging).
    """

    default_owner: str = "0x0000000000000000000000000000000000000001"
    _records: dict[str, _StubRecord] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def register(
        self,
        ens_subname: str,
        kb_cid_hash: bytes | str,
        *,
        signer_account: Any | None = None,
    ) -> dict[str, Any] | str:
        kb_bytes = _normalize_kb_hash(kb_cid_hash)
        existing = self._records.get(ens_subname)
        if existing is not None and existing.active:
            raise ValueError("AlreadyRegistered")
        owner = (
            to_checksum_address(signer_account.address)
            if signer_account is not None and hasattr(signer_account, "address")
            else self.default_owner
        )
        self._records[ens_subname] = _StubRecord(
            owner=owner,
            ens_subname=ens_subname,
            kb_cid_hash=kb_bytes,
            registered_at=datetime.now(tz=UTC),
            active=True,
        )
        call_log = {
            "fn": "register",
            "ens_subname": ens_subname,
            "kb_cid_hash": "0x" + kb_bytes.hex(),
            "signed": signer_account is not None,
        }
        self.calls.append(call_log)
        if signer_account is None:
            return {
                "to": "0x0000000000000000000000000000000000000000",
                "data": f"register:{ens_subname}",
                "value": 0,
            }
        return "0x" + ("ab" * 32)

    async def deactivate(self, ens_subname: str, *, caller: str) -> None:
        record = self._records.get(ens_subname)
        if record is None or to_checksum_address(record.owner) != to_checksum_address(caller):
            raise ValueError("NotOwner")
        record.active = False
        self.calls.append({"fn": "deactivate", "ens_subname": ens_subname})

    async def update_kb(
        self,
        ens_subname: str,
        new_kb_cid_hash: bytes | str,
        *,
        caller: str,
    ) -> None:
        record = self._records.get(ens_subname)
        if record is None or to_checksum_address(record.owner) != to_checksum_address(caller):
            raise ValueError("NotOwner")
        record.kb_cid_hash = _normalize_kb_hash(new_kb_cid_hash)
        self.calls.append(
            {
                "fn": "update_kb",
                "ens_subname": ens_subname,
                "kb_cid_hash": "0x" + record.kb_cid_hash.hex(),
            }
        )

    async def get(self, ens_subname: str) -> AgentRecord | None:
        record = self._records.get(ens_subname)
        if record is None:
            return None
        return AgentRecord(
            owner=to_checksum_address(record.owner),
            ens_subname=record.ens_subname,
            kb_cid_hash="0x" + record.kb_cid_hash.hex(),
            registered_at=record.registered_at,
            active=record.active,
        )

    async def is_active(self, ens_subname: str) -> bool:
        record = self._records.get(ens_subname)
        return record is not None and record.active


def load_deployment(chain_id: int, *, base_dir: Path | None = None) -> dict[str, Any] | None:
    """Read ``contracts/deployments/<chain_id>.json``.

    Returns the parsed JSON or ``None`` if the file is missing. The
    expected shape is::

        {"address": "0x...", "abi": [...], "deployedAt": "<iso8601>", "deployedBy": "0x..."}

    Args:
        chain_id: EVM chain id of the network the contract was
            deployed to.
        base_dir: Override the default ``contracts/deployments``
            directory. Used by tests; production callers should leave
            it ``None``.
    """
    root = base_dir if base_dir is not None else Path("contracts") / "deployments"
    path = root / f"{chain_id}.json"
    if not path.exists():
        return None
    parsed: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return parsed
