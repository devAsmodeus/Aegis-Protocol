# Aegis Protocol

> Trustworthy AI support agent for Web3 — ENS-verified identity, on-chain context, TEE-verified inference on 0G.

[![CI](https://github.com/devAsmodeus/Aegis-Protocol/actions/workflows/ci.yml/badge.svg)](https://github.com/devAsmodeus/Aegis-Protocol/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

A self-deployable AI support agent for Web3 communities (DAOs, protocols, dApps). Aegis Protocol solves a uniquely-Web3 problem: scammers impersonate official support in Discord and Telegram channels and drain user wallets. Generic chatbots (Intercom, Drift) cannot help — they have no on-chain context, no verifiable identity, and no cryptographic proof of inference.

## Quickstart

Pick your language and follow the step-by-step guide:

- 🇬🇧 **English:** [docs/QUICKSTART.en.md](docs/QUICKSTART.en.md)
- 🇷🇺 **Русский:** [docs/QUICKSTART.ru.md](docs/QUICKSTART.ru.md)

For a five-minute end-to-end demo (no docker required), see [docs/DEMO.md](docs/DEMO.md) or run:

```bash
uv run python -m scripts.demo_walkthrough
```

## What makes Aegis different

| | Generic chatbot | **Aegis Protocol** |
|---|---|---|
| Identity verification | platform username | **ENS subname** (`support.project.eth`) |
| On-chain context | ❌ | ✅ wallet, tx, protocol-state lookup |
| Live protocol state | ❌ static docs | ✅ live `eth_call` against contracts |
| Transaction simulation | ❌ | ✅ anti-rug-pull guard |
| Inference proof | trust the platform | **TEE on 0G Compute** |
| Audit trail | proprietary logs | **on-chain (0G DA)** |
| Self-host option | ❌ | ✅ open-source |

## Architecture (high level)

```
[User in Telegram/Discord]
            ↓
[Channel Adapter] ←─→ [Agent Runtime]
                              ↓
                ┌─────────────┼──────────────┐
                ↓             ↓              ↓
          [0G Storage]  [0G Compute TEE]  [0G DA]
          docs+embed    LLM inference      audit
                ↓             ↓              ↓
          [Hybrid Search]     ↓              ↓
          BM25+dense+RRF      ↓              ↓
                ↓             ↓              ↓
          [On-chain Tools] ───┘              ↓
          ├─ wallet lookup                   ↓
          ├─ tx simulation                   ↓
          ├─ live protocol state             ↓
          ├─ ENS resolver                    ↓
          └─ AegisRegistry                   ↓
                ↓                            ↓
          [Verified Response] ───────────────┘
                ↓
          [Receipt on 0G Chain]
                ↓
          [Reply via channel → User]

  (cron) ──→ [/v1/keeper] ──→ [KeeperRegistry] ──→ scheduled tasks
  (admin) ─→ [/v1/admin]  ──→ read-only audit + agent listing
```

Full architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Tech stack

- **Backend:** Python 3.12, FastAPI, async SQLAlchemy 2, asyncpg
- **Storage:** PostgreSQL 16, Redis 7, Qdrant
- **AI/RAG:** FastEmbed, BM25 + RRF hybrid search, FlashRank reranker
- **Web3:** 0G Storage / Compute / DA / Chain, ENS, web3.py, Solidity 0.8.24
- **Channels:** AIOgram (Telegram), discord.py (Discord)
- **Tooling:** uv, Ruff, mypy, pytest, pre-commit, GitHub Actions

## Components by prize track

| Track | Modules | What it delivers |
|---|---|---|
| **0G — Best Autonomous Agents** | `aegis/agent/`, `aegis/rag/`, `aegis/retrieval/` | Bounded async tool-loop runtime, hybrid retrieval, content-hashed receipts. |
| **ENS** | `aegis/chain/ens.py`, `aegis/chain/ens_subname.py`, `aegis/chain/registry.py`, `contracts/AegisRegistry.sol` | Forward / reverse ENS resolution, EIP-137 hashing helpers, on-chain agent registry. |
| **KeeperHub** | `aegis/keeper/`, `aegis/api/keeper.py` | Scheduled task infrastructure (`ScheduledTask`/`KeeperRegistry`) + HMAC-authenticated `/v1/keeper/tasks/{name}/run` webhook. |
| **Admin / observability** | `aegis/api/admin.py` | Bearer-protected read-only API for tenant listing, receipt audit, upstream healthcheck. |

## Setup

See [docs/QUICKSTART.en.md](docs/QUICKSTART.en.md) (or [docs/QUICKSTART.ru.md](docs/QUICKSTART.ru.md)) for the full step-by-step guide. The short version:

```bash
git clone https://github.com/devAsmodeus/Aegis-Protocol.git
cd Aegis-Protocol
uv sync
docker compose up -d
cp .env.example .env
uv run alembic upgrade head
uv run uvicorn aegis.main:app --reload
```

Verify: `curl http://localhost:8000/health` → `{"status":"ok","version":"0.1.0"}`.

## Demo

```bash
uv run python -m scripts.demo_walkthrough
```

Prints a captioned transcript covering registry → agent → receipt → ENS verification → keeper task. Pure stubs, no docker, no network.

For the judge-facing walkthrough see [docs/DEMO.md](docs/DEMO.md).

## Development

```bash
# Install pre-commit hooks
uv run pre-commit install

# Pre-commit gates (must all be green before each commit, per CLAUDE.md §3)
uv run pytest -m "not integration"
uv run ruff check . && uv run ruff format --check .
uv run mypy aegis
```

## Hackathon context

Built for [ETHGlobal Open Agents 2026](https://ethglobal.com/events/openagents) (Apr 24 – May 3, 2026).

**Targeting prize tracks:**
- 🏆 **0G — $15,000** (Track 2: Best Autonomous Agents) — primary
- 🌐 **ENS — $5,000** (Best ENS Integration)
- ⚙️ **KeeperHub — $5,000** (Best Innovative Use)

AI tools used during development are disclosed in [docs/AI_USAGE.md](docs/AI_USAGE.md) per ETHGlobal compliance rules.

## License

MIT — see [LICENSE](LICENSE).

## Contact

- **Author:** Pavel Kruglikovski
- **Telegram:** [@AsmodeusGL](https://t.me/AsmodeusGL)
- **Email:** p.kruglikovskii@gmail.com
