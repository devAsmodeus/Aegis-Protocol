# AI Tool Usage Disclosure

> Required by ETHGlobal hackathon rules. Documents which parts of this project were developed with AI-assisted tools, in the spirit of transparency.

## Tools used

| Tool | Vendor | Purpose |
|---|---|---|
| Claude Code (Opus 4.7) | Anthropic | Pair-programming assistant for scaffolding, code generation, planning, and code review |

## Areas with AI assistance

This file is updated as the project grows. Each entry names the area, the tool, and the nature of the assistance.

### Day 1 — scaffolding (2026-04-27)

- **Project skeleton** (Claude Code): generated `pyproject.toml`, `.gitignore`, `LICENSE`, `README.md`, `.env.example` from a written plan.
- **FastAPI app structure** (Claude Code): generated `aegis/main.py`, `aegis/config.py` (Pydantic Settings), `aegis/api/routes.py` (`/health` endpoint), and the corresponding async test in `tests/test_health.py`.
- **`docker-compose.yml`** (Claude Code): drafted services + healthchecks for postgres, redis, qdrant.
- **CI/CD configuration** (Claude Code): drafted GitHub Actions workflows (CI, CodeQL, Dependabot, release-please), pre-commit config, and PR/issue templates.
- **`docs/ARCHITECTURE.md`** (Claude Code): drafted architecture overview based on the planning notes in the author's private Obsidian vault.

### Day 2 — data & retrieval (2026-04-30)

- **`aegis/db/`** (Claude Code, PR #22): drafted multi-tenant ORM (`Tenant`, `Conversation`, `Message`, `Receipt`), Alembic environment + initial migration, async SQLAlchemy session factory. Schema decisions (UUID PKs, `TimestampMixin`, content-hash receipts) come from the author's planning notes.
- **`aegis/retrieval/`** (Claude Code, PR #2): drafted hybrid retrieval module — `Retriever`/`Reranker` `Protocol`s, `RetrievalQuery`/`RetrievalHit` types with canonical `content_hash`, Reciprocal Rank Fusion, in-memory `StaticRetriever`/`IdentityReranker` stubs for unit tests, Qdrant-backed dense (`QdrantDenseRetriever`, FastEmbed `BAAI/bge-small-en-v1.5`) and sparse BM25 (`QdrantBM25Retriever`, FastEmbed `Qdrant/bm25`) adapters, and the `HybridPipeline` orchestrator. Hybrid-search pattern (BM25 + dense + RRF) is referenced architecturally from the author's prior production project Raggy; no code is reused.
- **CodeQL config** (Claude Code, PR #23): drafted `.github/codeql/codeql-config.yml` to suppress false-positive `py/unused-*` findings on Alembic migration boilerplate and side-effect imports in tests.
- **release-please PAT wiring** (Claude Code, PR #24): drafted optional `RELEASE_PLEASE_TOKEN` support in `.github/workflows/release-please.yml` so release PRs trigger CI/CodeQL automatically.

## What is NOT AI-generated

- The product concept, prize-track strategy, and architecture decisions originate from the author's planning sessions documented in `Compass/01-Projects/aegis-protocol/overview.md` (private Obsidian vault).
- Wallet keys, ENS names, deployment addresses, and any signed-on-chain artifacts are produced by the author manually, never by AI.
- Final review, manual testing, and the demo video are done by the author.

## Reference patterns (architecture only, not code)

Per ETHGlobal rule that all code must be new (≥ 2026-04-24), the author's prior production projects are referenced for **architectural patterns only**. No code is copy-pasted:

- **Raggy** (production RAG system, MEGATOP) — hybrid-search pattern (BM25 + dense + RRF) reference for `aegis/rag/search.py`, to be implemented in Day 3.
- **OpenClaw** (Bitrix24 plugin, author's prior work) — async tool-loop pattern reference for `aegis/agent/runtime.py` (Day 4) and channel-adapter pattern reference for `aegis/channels/{telegram,discord}.py` (Day 5).

## Contact

If you have questions about AI usage in this project, contact the author at p.kruglikovskii@gmail.com.
