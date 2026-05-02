# Quickstart (English)

> First-run setup for Aegis Protocol on a single dev machine.
> Russian version: [QUICKSTART.ru.md](QUICKSTART.ru.md).

## Prerequisites

| Tool | Why | How to install |
|---|---|---|
| Python 3.12+ | Project runtime | <https://www.python.org/downloads/> |
| uv | Package manager + lockfile | `pip install uv` or follow <https://docs.astral.sh/uv/> |
| Docker (with Compose) | Postgres + Redis + Qdrant | <https://docs.docker.com/get-docker/> |
| Git | Source control | OS-specific |
| (Optional) 0G testnet RPC | Real on-chain demo | <https://docs.0g.ai> |
| (Optional) Telegram bot token | Telegram channel demo | `@BotFather` |
| (Optional) Discord bot token | Discord channel demo | <https://discord.com/developers> |

## 1. Clone and install

```bash
git clone https://github.com/devAsmodeus/Aegis-Protocol.git
cd Aegis-Protocol
uv sync
```

Optional extras (install only what you need):

```bash
uv sync --extra rerank      # FlashRank cross-encoder reranker
uv sync --extra telegram    # AIOgram-backed Telegram channel
uv sync --extra discord     # discord.py-backed Discord channel
uv sync --extra contracts   # py-solc-x for the registry deploy script
```

## 2. Bring up infrastructure

```bash
docker compose up -d
```

This starts:

- `postgres` — multi-tenant database (port 5432)
- `redis` — cache (port 6379)
- `qdrant` — vector store (port 6333)

Verify with:

```bash
docker compose ps
```

## 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env`. Required for a basic boot:

```dotenv
DATABASE_URL=postgresql+asyncpg://aegis:aegis_dev_password@localhost:5432/aegis
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333
```

Optional for individual demos:

| Variable | Why |
|---|---|
| `ETH_RPC_URL` | Real ENS resolution. Use Sepolia or mainnet. |
| `ZEROG_RPC_URL` / `ZEROG_PRIVATE_KEY` | Deploy `AegisRegistry.sol` to 0G testnet. **Testnet only.** |
| `ENS_PARENT_DOMAIN` | The project's parent ENS, e.g. `aegis-protocol.eth`. |
| `TELEGRAM_BOT_TOKEN` | Run the Telegram adapter. |
| `DISCORD_BOT_TOKEN` | Run the Discord adapter. |
| `KEEPER_SIGNING_SECRET` | HMAC secret the keeper webhook authenticates against. Without it the route returns 503. |
| `ADMIN_API_TOKEN` | Bearer token for `/v1/admin/*`. |

## 4. Apply database migrations

```bash
uv run alembic upgrade head
```

## 5. Run the API

```bash
uv run uvicorn aegis.main:app --reload
```

Smoke test:

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.1.0"}

curl http://localhost:8000/v1/keeper/tasks
# {"tasks":["healthcheck_upstreams","refresh_documents","rotate_agent_sessions"]}
```

## 6. Run the test suite

```bash
uv run pytest -m "not integration"
uv run ruff check . && uv run ruff format --check .
uv run mypy aegis
```

Default CI runs without docker; the integration suite (real Postgres /
Qdrant / Redis / RPC) is opt-in via `-m integration`.

## 7. Run the demo walkthrough

```bash
uv run python -m scripts.demo_walkthrough
```

This prints a captioned transcript covering registry → agent → receipt
→ ENS verification → keeper task. No network, no docker.

## Optional: enable Telegram

```bash
uv sync --extra telegram
export TELEGRAM_BOT_TOKEN=...
# then wire `aegis/channels/telegram.py:TelegramChannel` into your
# entry script — see the in-memory adapter for a tiny example.
```

## Optional: enable Discord

```bash
uv sync --extra discord
export DISCORD_BOT_TOKEN=...
# wire `aegis/channels/discord.py:DiscordChannel` similarly.
```

## Optional: deploy `AegisRegistry.sol` to 0G testnet

```bash
uv sync --extra contracts
export ZEROG_RPC_URL=...
export ZEROG_PRIVATE_KEY=...        # testnet ONLY
uv run python -m contracts.scripts.deploy_registry
```

The script refuses to run on a known mainnet chain id (Ethereum,
Optimism, Polygon, Arbitrum, Base) and refuses unless
`APP_ENV=development`.

## Optional: register an ENS subname

```python
from aegis.chain.ens_subname import register_subname
# Returns an unsigned tx dict. Sign + broadcast externally.
```

## Optional: configure keeper webhooks

KeeperHub (or any cron caller) signs the request body with HMAC-SHA256
using `KEEPER_SIGNING_SECRET`:

```bash
SECRET=$KEEPER_SIGNING_SECRET
BODY='{}'
SIG=$(printf "%s" "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')
curl -X POST http://localhost:8000/v1/keeper/tasks/healthcheck_upstreams/run \
  -H "X-Aegis-Keeper-Signature: $SIG" \
  -d "$BODY"
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `connection refused` to localhost:5432/6379/6333 | Docker is not running. | `docker compose up -d` |
| `alembic.util.exc.CommandError: Can't locate revision identified by 'XYZ'` | DB has a different head than the codebase. | Drop the dev DB and re-run `alembic upgrade head`, or write a new migration. |
| `solcx.exceptions.SolcNotInstalled` | `contracts` extra not installed or solc 0.8.24 not cached. | `uv sync --extra contracts && python -c "import solcx; solcx.install_solc('0.8.24')"` |
| `web3.exceptions.ConnectionError` | `ETH_RPC_URL` / `ZEROG_RPC_URL` unset or unreachable. | Set the env var or pick a different demo step. |
| `mypy` fails on `web3` / `aiogram` / `discord` types | Optional extras not installed in the active venv. | `uv sync --extra <name>` for the missing one, or rely on the existing `[[tool.mypy.overrides]]` section in `pyproject.toml`. |

## Where to read next

- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — full architecture.
- [docs/DEMO.md](DEMO.md) — demo script for judges.
- [docs/AI_USAGE.md](AI_USAGE.md) — ETHGlobal AI-tool disclosure.
