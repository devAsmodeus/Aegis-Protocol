# `contracts/` — On-chain registry

This directory holds the Solidity source for `AegisRegistry.sol` and the
Python helpers that compile and deploy it to a testnet. Per
[`CLAUDE.md`](../CLAUDE.md) §3, the workflow here is **testnet-only** and
**never auto-signs in production**.

## What the contract guarantees

`AegisRegistry.sol` (Solidity 0.8.24, MIT, no external deps) maps an
ENS subname to an `AgentRecord{owner, ensSubname, kbCidHash, registeredAt, active}`.
The on-chain surface is:

| Function | Effect | Guard |
|---|---|---|
| `register(ensSubname, kbCidHash)` | Create / reactivate a record, owner = `msg.sender` | reverts `AlreadyRegistered` if the name is currently active |
| `deactivate(ensSubname)` | Mark the record inactive | reverts `NotOwner` |
| `updateKb(ensSubname, newKbCidHash)` | Rotate the KB CID hash | reverts `NotOwner` |
| `get(ensSubname)` | Read the full record | returns zero-struct if missing |
| `isActive(ensSubname)` | Cheap "live agent?" boolean | — |

Storage key is `keccak256(abi.encodePacked(ensSubname))`.

## Trust model

See [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md#on-chain-registry-trust-model).
The short version: no proxy, no admin, no upgrade. The contract is
immutable bytecode plus the project owner's signing key.

## Compile + deploy

The deploy path uses pure web3.py + `py-solc-x` — no Hardhat install
required. The `contracts` extra installs the compiler bridge:

```bash
uv sync --extra contracts
```

First run downloads solc 0.8.24 via `py-solc-x`. Subsequent runs reuse
the cached binary.

To deploy to a 0G testnet (set `ZEROG_RPC_URL`, `ZEROG_PRIVATE_KEY`,
and `APP_ENV=development` in `.env` first):

```bash
uv run python -m contracts.scripts.deploy_registry --network 0g-testnet
```

The script:

1. Refuses to run if `app_env != "development"` or the private key is
   unset.
2. Refuses to run if the live chain id matches a known mainnet
   (Ethereum, Optimism, Polygon, Arbitrum, Base).
3. Compiles `contracts/AegisRegistry.sol` with solc 0.8.24.
4. Writes `contracts/deployments/<chain_id>.json` with
   `{address, abi, deployedAt, deployedBy, txHash, network}`.

`contracts/deployments/*.json` is gitignored. **Do not commit real
deployment artifacts.**

## Source

- Contract: [`AegisRegistry.sol`](AegisRegistry.sol)
- Deployer: [`scripts/deploy_registry.py`](scripts/deploy_registry.py)
- Python client: [`aegis/chain/registry.py`](../aegis/chain/registry.py)
- Subname helper: [`aegis/chain/ens_subname.py`](../aegis/chain/ens_subname.py)
