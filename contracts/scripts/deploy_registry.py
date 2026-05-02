"""Deploy :file:`contracts/AegisRegistry.sol` to a 0G testnet.

Pure web3.py + py-solc-x — no Hardhat. Run with::

    uv run python -m contracts.scripts.deploy_registry --network 0g-testnet

Behavior:

* Reads :class:`aegis.config.Settings.zerog_rpc_url` and
  :class:`aegis.config.Settings.zerog_private_key`.
* Refuses to run if ``app_env != "development"`` or if
  ``zerog_private_key`` is missing — per ``CLAUDE.md`` §3 (testnet
  only, never auto-sign on mainnet).
* Refuses to run if the live chain id matches a known mainnet
  (1, 10, 137, 42161, 8453).
* Compiles the contract with solc 0.8.24 (installs on first run via
  py-solc-x).
* Writes ``contracts/deployments/<chain_id>.json`` with the address,
  ABI, deployedAt, deployedBy.

This script is intentionally NOT importable as a runtime dependency
of the agent — it lives behind the ``contracts`` extra so the default
install stays slim.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Known L1/L2 chain ids we MUST NOT auto-deploy to. Defensive list
# pulled from public registries; expand only when a new mainnet must
# be explicitly blocked.
_MAINNET_CHAIN_IDS = frozenset(
    {
        1,  # Ethereum mainnet
        10,  # Optimism
        137,  # Polygon PoS
        42161,  # Arbitrum One
        8453,  # Base
    }
)

_SOLC_VERSION = "0.8.24"


def _compile_contract(source_path: Path) -> tuple[list[dict[str, Any]], str]:
    """Compile :file:`AegisRegistry.sol` and return (ABI, bytecode).

    Lazily imports :mod:`solcx` so the script fails with a friendly
    message if the optional ``contracts`` extra is not installed.
    """
    try:
        import solcx
    except ImportError as exc:
        raise SystemExit(
            "py-solc-x is not installed. Run `uv sync --extra contracts` first."
        ) from exc

    if _SOLC_VERSION not in [str(v) for v in solcx.get_installed_solc_versions()]:
        print(f"[deploy] installing solc {_SOLC_VERSION}...", flush=True)
        solcx.install_solc(_SOLC_VERSION)

    solcx.set_solc_version(_SOLC_VERSION)
    source = source_path.read_text(encoding="utf-8")
    compiled = solcx.compile_source(
        source,
        output_values=["abi", "bin"],
        solc_version=_SOLC_VERSION,
    )
    # Output keys look like "<stdin>:AegisRegistry"; pick the first
    # entry whose suffix is :AegisRegistry.
    for key, artifact in compiled.items():
        if key.endswith(":AegisRegistry"):
            abi = artifact["abi"]
            bytecode = artifact["bin"]
            return abi, bytecode
    raise RuntimeError(f"AegisRegistry not found in compile output: {list(compiled)}")


async def _deploy(
    rpc_url: str,
    private_key: str,
    abi: list[dict[str, Any]],
    bytecode: str,
) -> dict[str, Any]:
    from eth_account import Account
    from web3 import AsyncHTTPProvider, AsyncWeb3

    w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
    chain_id = int(await w3.eth.chain_id)
    if chain_id in _MAINNET_CHAIN_IDS:
        raise SystemExit(
            f"Refusing to deploy: chain id {chain_id} is a known mainnet. Testnet only."
        )

    account = Account.from_key(private_key)
    print(f"[deploy] chain_id={chain_id} deployer={account.address}", flush=True)

    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    nonce = await w3.eth.get_transaction_count(account.address)
    tx = await contract.constructor().build_transaction({"from": account.address, "nonce": nonce})
    signed = account.sign_transaction(tx)
    tx_hash = await w3.eth.send_raw_transaction(signed.rawTransaction)
    print(f"[deploy] tx={'0x' + bytes(tx_hash).hex()}", flush=True)

    receipt = await w3.eth.wait_for_transaction_receipt(tx_hash)
    address = receipt["contractAddress"]
    print(f"[deploy] deployed at {address}", flush=True)

    return {
        "chain_id": chain_id,
        "address": address,
        "abi": abi,
        "tx_hash": "0x" + bytes(tx_hash).hex(),
        "deployed_by": account.address,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy AegisRegistry.sol")
    parser.add_argument(
        "--network",
        default="0g-testnet",
        help="Logical network name (informational; chain id is read from the RPC).",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("contracts") / "AegisRegistry.sol",
        help="Path to the .sol source.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("contracts") / "deployments",
        help="Directory to write the deployment JSON to.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    from aegis.config import get_settings

    settings = get_settings()
    if settings.app_env != "development":
        print(
            f"[deploy] refusing: app_env={settings.app_env}; testnet deploy is dev-only.",
            file=sys.stderr,
        )
        return 2
    if not settings.zerog_private_key:
        print("[deploy] refusing: ZEROG_PRIVATE_KEY is not set.", file=sys.stderr)
        return 2
    if not settings.zerog_rpc_url:
        print("[deploy] refusing: ZEROG_RPC_URL is not set.", file=sys.stderr)
        return 2

    if not args.source.exists():
        print(f"[deploy] source missing: {args.source}", file=sys.stderr)
        return 2

    abi, bytecode = _compile_contract(args.source)
    result = asyncio.run(_deploy(settings.zerog_rpc_url, settings.zerog_private_key, abi, bytecode))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"{result['chain_id']}.json"
    payload = {
        "address": result["address"],
        "abi": result["abi"],
        "deployedAt": datetime.now(tz=UTC).isoformat(),
        "deployedBy": result["deployed_by"],
        "txHash": result["tx_hash"],
        "network": args.network,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[deploy] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
