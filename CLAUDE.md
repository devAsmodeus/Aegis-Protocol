# CLAUDE.md — Working rules for Aegis Protocol

This file is read at the start of every Claude Code session in this repo. It encodes the hard rules, why they exist, and how to add new ones. Keep it short. Bullet points beat paragraphs. Concrete commands beat prose.

## 1. Self-improvement protocol

When I make a mistake, take a long detour, or you correct my approach — invoke the trigger:

> **"Reflect on this mistake. Abstract and generalize the learning. Append it to CLAUDE.md following the META rules in §5."**

On that trigger I will:
1. Name the root cause of the mistake in one sentence.
2. Generalize it into a rule that prevents the whole class of error, not just this instance.
3. Append the rule to §3 (absolute) or §4 (heuristic) under the right subsection.
4. Keep it short — see META rules in §5.

If a rule fires twice (you have to correct me on the same class of mistake again), promote it from §6 to §3.

## 2. Project context (load-bearing facts)

- ETHGlobal Open Agents 2026 hackathon. All code must be **≥ 2026-04-24** (no copy-paste from prior projects).
- Solo developer. Submission deadline: **2026-05-03**.
- Stack: Python 3.12, FastAPI, async SQLAlchemy 2 + asyncpg, Postgres 16, Redis 7, Qdrant, FastEmbed, web3.py.
- Packaging: `uv`. Lint: `ruff`. Types: `mypy --strict`. Tests: `pytest` (`asyncio_mode = "auto"`).
- Prize tracks: 0G (primary, Best Autonomous Agents), ENS, KeeperHub. See `README.md`.

## 3. Absolute rules — NEVER / ALWAYS

### Git workflow
- **NEVER** push directly to `main`. Always: feature branch → PR → merge through GitHub UI.
- **NEVER** `git push --force` to a shared branch.
- **NEVER** `--amend` a commit that has been pushed.
- **NEVER** use `--no-verify`, `--no-gpg-sign`, or any hook bypass. If a hook fails, fix the underlying issue.
- **ALWAYS** branch from up-to-date `main`: `git checkout main && git pull --ff-only && git checkout -b feat/<topic>`.

### Secrets & on-chain
- **NEVER** commit `.env`, private keys, mnemonics, signed transaction blobs, deployment artifacts.
- **NEVER** use a mainnet private key. Testnet only.
- **NEVER** generate, sign, or broadcast on-chain transactions automatically. Wallet keys are user-produced (per `docs/AI_USAGE.md`).

### CI / tests
- **ALWAYS** mark tests that need Postgres / Qdrant / Redis / 0G / RPC / Telegram / Discord with `@pytest.mark.integration`. Default CI must stay green without docker.
- **ALWAYS** run before each commit:
  ```bash
  uv run pytest -m "not integration"
  uv run ruff check . && uv run ruff format --check .
  uv run mypy aegis
  ```
- **NEVER** mark a test as `integration` just to silence a flaky failure. Fix the test or quarantine it explicitly with `@pytest.mark.skip(reason="...")`.

### Schema / data
- **ALWAYS** use `sqlalchemy.Uuid` primary keys and the `TimestampMixin` for new ORM models in `aegis/db/`.
- **ALWAYS** store `Receipt.retrieval_ids` as **content-hashes** (sha256 of chunk text), never Qdrant point IDs. The receipt must be reproducible without trusting Qdrant.
- **NEVER** edit a migration that is already on `main`. Add a new migration instead.

### Disclosure
- **ALWAYS** update `docs/AI_USAGE.md` when adding a new top-level module under `aegis/`. ETHGlobal compliance requires it.
- **ALWAYS** disclose AI tooling in commits that introduce AI-generated structure (use the existing Day-N entry pattern).

## 4. Heuristics — defaults that bend with reason

- Default embedding model is `BAAI/bge-small-en-v1.5` (384-dim, set in `aegis/config.py`). Changing it requires recreating Qdrant collections — make it a deliberate decision, not a drive-by edit.
- Prefer **adding** schema columns over **modifying** them. Migrations are append-only history.
- For new endpoints, mount under `/v1/...` so future versioning is cheap.
- For tests that need a real DB and call `alembic.command.*`, prefer a **sync** test function with `asyncio.run(...)` for verification — alembic spawns its own loop and conflicts with `pytest-asyncio`'s outer loop.
- New top-level modules under `aegis/` should ship with at least one unit test that runs without docker (`-m "not integration"`).
- Background interfaces (LLMClient, ReceiptSink, Retriever) are `Protocol`s with stub + real impls; keep stubs deterministic so e2e tests are stable.

## 5. META — how to add or edit rules

Follow these when appending to §3 / §4 / §6:

- **Lead with the directive.** Start with `NEVER` or `ALWAYS`. No softening verbs ("try to", "consider").
- **Lead with why only when non-obvious.** One short clause. Skip if the directive is self-evident.
- **Be concrete.** Include the actual command, file path, symbol, or marker. No prose paragraphs.
- **Compress.** If two rules collapse into one, collapse them. If a rule duplicates something already in §3, delete the duplicate.
- **No bad-example blocks for trivial rules.** No "warning signs" sections. No anti-pattern blocks that just restate the rule.
- **Group by topic.** Add under the right subsection. If no subsection fits, create one with a single short `### heading`.
- **Don't date-stamp.** Rules are stable; CHANGELOG / git blame already track when something landed.
- **One rule = one bullet.** If you need two bullets, you have two rules.

## 6. Open questions / lessons-in-progress

(Empty. New observations that haven't yet hardened into a rule go here. Promote to §3 or §4 the second time the same class of correction is needed.)
