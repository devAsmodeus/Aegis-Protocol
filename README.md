# Aegis Protocol

> Trustworthy AI support agent for Web3 — ENS-verified identity, on-chain context, TEE-verified inference on 0G.

[![CI](https://github.com/devAsmodeus/Aegis-Protocol/actions/workflows/ci.yml/badge.svg)](https://github.com/devAsmodeus/Aegis-Protocol/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

A self-deployable AI support agent for Web3 communities (DAOs, protocols, dApps). Aegis Protocol solves a uniquely-Web3 problem: scammers impersonate official support in Discord and Telegram channels and drain user wallets. Generic chatbots (Intercom, Drift) cannot help — they have no on-chain context, no verifiable identity, and no cryptographic proof of inference.

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
          └─ ENS resolver                    ↓
                ↓                            ↓
          [Verified Response] ───────────────┘
                ↓
          [Receipt on 0G Chain]
                ↓
          [Reply via channel → User]
```

Full architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Tech stack

- **Backend:** Python 3.12, FastAPI, async SQLAlchemy, asyncpg
- **Storage:** PostgreSQL (tenants), Redis (cache), Qdrant (vectors)
- **AI/RAG:** FastEmbed, BM25 + RRF hybrid search, FlashRank reranker
- **Web3:** 0G Storage / Compute / DA / Chain, ENS, web3.py
- **Channels:** AIOgram (Telegram), discord.py (Discord)
- **Tooling:** uv, Ruff, mypy, pytest, pre-commit, GitHub Actions

## Setup

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker.

```bash
git clone https://github.com/devAsmodeus/Aegis-Protocol.git
cd Aegis-Protocol

# Install dependencies
uv sync

# Spin up infra (postgres, redis, qdrant)
docker compose up -d

# Apply database migrations
uv run alembic upgrade head

# Run the API
uv run uvicorn aegis.main:app --reload
```

Verify: `curl http://localhost:8000/health` → `{"status":"ok","version":"0.1.0"}`.

## Development

```bash
# Install pre-commit hooks
uv run pre-commit install

# Lint + format
uv run ruff check .
uv run ruff format .

# Type check
uv run mypy src

# Tests
uv run pytest -v
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
