"""Agent-runtime :class:`Tool` wrappers for on-chain helpers.

The Day 4 tool-loop (:mod:`aegis.agent.runtime`) dispatches tools by
name. These three wrappers expose the chain helpers to the loop:

* ``resolve_ens`` — forward + reverse ENS lookup.
* ``inspect_wallet`` — balance / nonce / recent txs.
* ``simulate_tx`` — dry-run with anti-rug-pull warnings.

Each :meth:`call` returns a :class:`~aegis.agent.types.ToolResult`
whose ``output`` is a short human-readable summary (so it lands cleanly
in the LLM transcript) and whose ``metadata`` carries the structured
JSON-serializable payload so downstream code (receipts, channel
adapters) can consume it without re-parsing strings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from aegis.agent.types import ToolResult
from aegis.chain.ens import EnsResolverProtocol
from aegis.chain.simulator import TxRequest, TxSimulatorProtocol
from aegis.chain.wallet import WalletInspectorProtocol


def _json_safe(value: Any) -> Any:
    """Coerce ``Decimal`` / Pydantic models into JSON-friendly forms."""
    if isinstance(value, Decimal):
        return format(value, "f")
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    return value


@dataclass(slots=True)
class ResolveEnsTool:
    """Wraps :class:`EnsResolverProtocol` for the agent runtime."""

    resolver: EnsResolverProtocol
    name: str = field(default="resolve_ens", init=False)
    description: str = field(
        default=(
            "Resolve an ENS name to a checksummed address, or look up "
            "the primary ENS name for an address. Use when the user "
            "mentions an ENS name (anything ending in '.eth') or asks "
            "who owns a given address."
        ),
        init=False,
    )

    @property
    def json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "ENS name to resolve."},
                "address": {
                    "type": "string",
                    "description": "Address for reverse lookup.",
                },
            },
            "additionalProperties": False,
        }

    async def call(self, arguments: dict[str, Any]) -> ToolResult:
        name = arguments.get("name")
        address = arguments.get("address")
        payload: dict[str, Any] = {}
        if isinstance(name, str) and name:
            payload["address"] = await self.resolver.resolve_name(name)
            payload["name"] = name
        elif isinstance(address, str) and address:
            payload["name"] = await self.resolver.reverse_lookup(address)
            payload["address"] = address
        else:
            payload = {"error": "missing 'name' or 'address'"}
        return ToolResult(
            name=self.name,
            output=json.dumps(_json_safe(payload), separators=(",", ":")),
            metadata=_json_safe(payload),
        )


@dataclass(slots=True)
class InspectWalletTool:
    """Wraps :class:`WalletInspectorProtocol` for the agent runtime."""

    inspector: WalletInspectorProtocol
    recent_tx_limit: int = 5
    name: str = field(default="inspect_wallet", init=False)
    description: str = field(
        default=(
            "Read on-chain context for a wallet: ETH balance, transaction "
            "nonce, and (when an indexer is configured) recent transactions. "
            "Use when the user asks about a wallet's activity or holdings."
        ),
        init=False,
    )

    @property
    def json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "Wallet address."},
            },
            "required": ["address"],
            "additionalProperties": False,
        }

    async def call(self, arguments: dict[str, Any]) -> ToolResult:
        address = str(arguments["address"])
        balance = await self.inspector.balance(address)
        nonce = await self.inspector.tx_count(address)
        recent = await self.inspector.recent_txs(address, limit=self.recent_tx_limit)
        payload = {
            "address": address,
            "balance_eth": format(balance, "f"),
            "tx_count": nonce,
            "recent_txs": [_json_safe(tx) for tx in recent],
        }
        return ToolResult(
            name=self.name,
            output=json.dumps(payload, separators=(",", ":")),
            metadata=payload,
        )


@dataclass(slots=True)
class SimulateTxTool:
    """Wraps :class:`TxSimulatorProtocol` for the agent runtime."""

    simulator: TxSimulatorProtocol
    name: str = field(default="simulate_tx", init=False)
    description: str = field(
        default=(
            "Dry-run a transaction via eth_call before the user signs it. "
            "Returns success/revert info and surfaces anti-rug-pull warnings "
            "(e.g. unlimited ERC-20 approvals)."
        ),
        init=False,
    )

    @property
    def json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "from_addr": {"type": "string"},
                "to_addr": {"type": "string"},
                "value_wei": {"type": "integer", "minimum": 0},
                "data": {"type": ["string", "null"]},
                "gas": {"type": ["integer", "null"], "minimum": 0},
            },
            "required": ["from_addr", "to_addr"],
            "additionalProperties": False,
        }

    async def call(self, arguments: dict[str, Any]) -> ToolResult:
        request = TxRequest(
            from_addr=str(arguments["from_addr"]),
            to_addr=str(arguments["to_addr"]),
            value_wei=int(arguments.get("value_wei", 0) or 0),
            data=arguments.get("data"),
            gas=arguments.get("gas"),
        )
        result = await self.simulator.simulate(request)
        payload = result.model_dump(mode="json")
        return ToolResult(
            name=self.name,
            output=json.dumps(payload, separators=(",", ":")),
            metadata=payload,
        )
