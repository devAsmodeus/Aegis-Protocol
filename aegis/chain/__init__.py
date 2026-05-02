"""On-chain context tools.

This package exposes async helpers the agent runtime uses to enrich
replies with on-chain facts:

* :mod:`aegis.chain.ens` — forward / reverse ENS lookups.
* :mod:`aegis.chain.wallet` — balance, tx-count, recent transactions.
* :mod:`aegis.chain.simulator` — ``eth_call``-based dry-run with
  anti-rug-pull warnings (e.g. unlimited ``approve`` allowance).
* :mod:`aegis.chain.tools` — :class:`~aegis.agent.protocol.Tool`
  wrappers so the Day 4 tool-loop can invoke them.

Per ``CLAUDE.md`` §3, anything that hits a real RPC must be marked
``@pytest.mark.integration``. The :class:`StubEnsResolver`,
:class:`StubWalletInspector` and :class:`StubTxSimulator` impls give
unit tests deterministic fixtures without docker or a real RPC.
"""

from __future__ import annotations

from aegis.chain.ens import EnsResolver, EnsResolverProtocol, StubEnsResolver
from aegis.chain.simulator import (
    SimulationResult,
    StubTxSimulator,
    TxRequest,
    TxSimulator,
    TxSimulatorProtocol,
)
from aegis.chain.tools import InspectWalletTool, ResolveEnsTool, SimulateTxTool
from aegis.chain.wallet import (
    StubWalletInspector,
    TxSummary,
    WalletInspector,
    WalletInspectorProtocol,
)

__all__ = [
    "EnsResolver",
    "EnsResolverProtocol",
    "InspectWalletTool",
    "ResolveEnsTool",
    "SimulateTxTool",
    "SimulationResult",
    "StubEnsResolver",
    "StubTxSimulator",
    "StubWalletInspector",
    "TxRequest",
    "TxSimulator",
    "TxSimulatorProtocol",
    "TxSummary",
    "WalletInspector",
    "WalletInspectorProtocol",
]
