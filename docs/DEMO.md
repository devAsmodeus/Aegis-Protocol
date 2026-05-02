# Aegis Protocol — demo walkthrough

> Five-minute live demo for ETHGlobal Open Agents 2026 judges.
> Companion script: [`scripts/demo_walkthrough.py`](../scripts/demo_walkthrough.py)
> (runs the same flow programmatically, no network needed).

## 30-second pitch

Generic chatbots (Intercom, Drift) cannot defend a Web3 community.
They have no on-chain context, no verifiable identity, and no proof
that the answer wasn't tampered with. Scammers exploit this every day
in Discord and Telegram, draining wallets with fake "support".

**Aegis Protocol** fixes the trust gap with three on-chain primitives:

1. **ENS subname identity** — `support.<project>.eth` resolves to a
   wallet the project controls. Impersonation is detectable.
2. **TEE-verified inference on 0G Compute** — every reply is signed by
   the model attestation; the audit trail lives on 0G DA.
3. **On-chain context tools** — wallet inspection and transaction
   simulation catch unlimited-allowance rug pulls before the user signs.

This demo proves all three end-to-end with the existing stubs, so
judges can rerun it without docker.

## Prize-track map

| Step | Track | What the judge sees |
|---|---|---|
| 1. Tenant + agent registration | **0G** + **ENS** | An on-chain registry record tying an ENS subname to a wallet. |
| 2. Document upload + RAG | **0G** | Tenant-scoped hybrid search (BM25 + dense + RRF). |
| 3. Telegram-style channel turn | **0G** | The agent answers a real user question and surfaces source hashes. |
| 4. Receipt | **0G** | A content-hashed receipt tying input → output → retrievals → model. |
| 5. ENS verifyability | **ENS** | `AegisRegistry.isActive("support.acme.eth")` returns true. |
| 6. Keeper task | **KeeperHub** | A KeeperHub-style cron call hits `/v1/keeper/tasks/.../run` and runs a health probe. |

## Step-by-step demo

### Step 0 — bring up infra (one-time, optional)

```bash
docker compose up -d                # postgres + redis + qdrant
uv sync                             # editable install
uv run alembic upgrade head         # apply migrations
uv run uvicorn aegis.main:app --reload &
curl -s http://localhost:8000/health
# -> {"status":"ok","version":"0.1.0"}
```

If you only have ten seconds, skip docker — every step below also runs
through the offline walkthrough script:

```bash
uv run python -m scripts.demo_walkthrough
```

### Step 1 — register a tenant + agent

The on-chain registry (`AegisRegistry.sol`, deployed in PR #2) is the
public source of truth for "which wallet runs which `support.<project>.eth`
agent". The walkthrough uses `StubAegisRegistry` so judges don't need
testnet ETH:

```bash
uv run python -m scripts.demo_walkthrough
```

Expected line:

```
>>> Step 1 — Registry: register agent (PR #2 / KeeperHub-adjacent)
    ENS subname: support.acme.eth
    active:      True
```

### Step 2 — upload a document

Static retriever stand-in for a 0G Storage upload. Real flow uses
`aegis/rag/service.py` (Day 3) backed by Qdrant. The walkthrough
hard-codes one chunk so the agent has something to cite.

### Step 3 — ask via the in-memory channel

The user sends "What is unlimited approval?". The agent runtime
dispatches `rag_search` via the tool-loop, then returns a
captioned answer:

```
>>> Step 2 — Channel + Agent runtime (Day 4/5)
    user:      What is unlimited approval?
    agent:     Treat unlimited token allowances as a red flag and never auto-sign them.
    tools:     rag_search
    model:     static-plan
```

### Step 4 — show the receipt

Per `CLAUDE.md` §3, receipts store **content-hashes** of retrieved
chunks, never Qdrant point IDs. The receipt is reproducible without
trusting the vector store:

```
>>> Step 3 — Receipt (Day 4 — verifiability)
    input_hash:    2a73164074ae9a79…
    output_hash:   3f400e37fd80d257…
    retrieval_ids: ['7cac841d…']
    tools_used:    ['rag_search']
```

### Step 5 — verify the agent on-chain

A user (or another bot) can independently check the agent is the real
one by calling the registry:

```
>>> Step 4 — ENS verifyability (Day 6/7)
    AegisRegistry.isActive('support.acme.eth'): True
```

### Step 6 — run a keeper task

Hit the keeper webhook with a signed body. In the demo we sign with a
test secret and receive the structured `TaskResult`:

```bash
SECRET=demo-secret
BODY='{}'
SIG=$(printf "%s" "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')
curl -sS -X POST http://localhost:8000/v1/keeper/tasks/healthcheck_upstreams/run \
  -H "X-Aegis-Keeper-Signature: $SIG" \
  -d "$BODY" | jq .
```

Expected (truncated):

```json
{
  "name": "healthcheck_upstreams",
  "success": true,
  "summary": "ok",
  "details": {"services": {"database": {"status": "skipped"}}}
}
```

(Set `KEEPER_SIGNING_SECRET=demo-secret` in your `.env` for the route
to accept the signature.)

### Step 7 — admin panel

The admin API gives the project operator a read-only window into the
registry + audit log:

```bash
curl -sS http://localhost:8000/v1/admin/agents \
  -H "Authorization: Bearer $ADMIN_API_TOKEN" | jq .

curl -sS http://localhost:8000/v1/admin/audit/<tenant_uuid> \
  -H "Authorization: Bearer $ADMIN_API_TOKEN" | jq .

curl -sS http://localhost:8000/v1/admin/healthz \
  -H "Authorization: Bearer $ADMIN_API_TOKEN" | jq .
```

## Reproducibility

Every step above is exercised by automated tests. The end-to-end demo
is regression-guarded by `tests/test_demo_walkthrough.py` so the
script can never silently break before submission.

```bash
uv run pytest tests/test_demo_walkthrough.py -v
```

## Why this matters for judges

- **0G** — TEE inference + DA audit trail + the Storage-backed KB. The
  receipt is the artifact judges should look at: it ties model_id,
  input hash, output hash, and retrieval-content hashes into a single
  reproducible record.
- **ENS** — `AegisRegistry.sol` plus `aegis/chain/ens_subname.py`
  expose the EIP-137 hashing and the agent-record lookup any client
  can use to defeat impersonation.
- **KeeperHub** — `aegis/keeper/` plus the HMAC-protected
  `/v1/keeper/tasks/{name}/run` endpoint give KeeperHub a stable hook
  to drive health checks, document re-embedding, and audit-log
  rotation on a cron schedule.
