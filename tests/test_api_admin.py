"""Unit tests for the ``/v1/admin`` router.

DB access is mocked via the ``get_db_session`` dependency override —
we inject a fake session whose ``execute`` returns a hand-rolled result
object. No docker, no asyncpg.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from aegis.api.dependencies import (
    get_db_session,
    get_keeper_registry,
    require_admin_bearer,
)
from aegis.config import Settings, get_settings
from aegis.db.models import Conversation, Message, Receipt, Tenant
from aegis.keeper import HealthcheckUpstreamsTask, KeeperRegistry, TaskResult
from aegis.main import create_app
from fastapi.testclient import TestClient


@dataclass(slots=True)
class _ScalarsAll:
    rows: list[Any]

    def all(self) -> list[Any]:
        return list(self.rows)


@dataclass(slots=True)
class _Result:
    rows: list[Any]
    pairs: list[tuple[Any, ...]]

    def scalars(self) -> _ScalarsAll:
        return _ScalarsAll(self.rows)

    def all(self) -> list[tuple[Any, ...]]:
        return list(self.pairs)


@dataclass(slots=True)
class _FakeSession:
    """Minimal stand-in for AsyncSession.

    Captures execute() statements and returns the matching `_Result`
    based on which kind of query the route emitted.
    """

    tenants: list[Tenant]
    pairs: list[tuple[Receipt, Message]]

    async def execute(self, statement: Any) -> _Result:
        compiled = str(statement)
        if "tenants" in compiled and "FROM tenants" in compiled:
            return _Result(rows=self.tenants, pairs=[])
        if "FROM receipts" in compiled or "JOIN" in compiled.upper():
            return _Result(rows=[], pairs=self.pairs)
        return _Result(rows=[], pairs=[])


def _build_app(
    *,
    admin_token: str | None,
    tenants: list[Tenant] | None = None,
    pairs: list[tuple[Receipt, Message]] | None = None,
    healthcheck_result: TaskResult | None = None,
) -> TestClient:
    app = create_app()
    fake_session = _FakeSession(tenants=tenants or [], pairs=pairs or [])

    async def _override_session() -> Any:
        yield fake_session

    def _override_settings() -> Settings:
        return Settings(admin_api_token=admin_token)

    registry = KeeperRegistry()
    if healthcheck_result is not None:

        @dataclass(slots=True)
        class _Stub:
            name: str = "healthcheck_upstreams"
            result: TaskResult = healthcheck_result  # type: ignore[assignment]

            async def run(self) -> TaskResult:
                return self.result

        registry.register(_Stub())
    else:
        registry.register(HealthcheckUpstreamsTask(settings=Settings()))

    def _override_registry() -> KeeperRegistry:
        return registry

    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[get_settings] = _override_settings
    app.dependency_overrides[get_keeper_registry] = _override_registry
    return TestClient(app)


def _make_tenant(name: str = "acme", ens: str | None = "support.acme.eth") -> Tenant:
    t = Tenant()
    t.id = uuid4()
    t.name = name
    t.ens_name = ens
    t.registry_addr = "0xabc"
    t.created_at = datetime.now(UTC)
    t.updated_at = datetime.now(UTC)
    return t


def _make_receipt_pair(tenant_id: Any) -> tuple[Receipt, Message]:
    conv = Conversation()
    conv.id = uuid4()
    conv.tenant_id = tenant_id
    msg = Message()
    msg.id = uuid4()
    msg.conversation_id = conv.id
    msg.role = "assistant"
    msg.content = "hi"
    rec = Receipt()
    rec.id = uuid4()
    rec.message_id = msg.id
    rec.input_hash = "i" * 64
    rec.output_hash = "o" * 64
    rec.model_id = "echo-llm"
    rec.tools_used = ["rag_search"]
    rec.retrieval_ids = ["h1", "h2"]
    rec.payload_json = {}
    rec.created_at = datetime.now(UTC)
    return rec, msg


def test_agents_returns_401_without_bearer() -> None:
    client = _build_app(admin_token="t0k3n")
    response = client.get("/v1/admin/agents")
    assert response.status_code == 401


def test_agents_returns_401_with_wrong_bearer() -> None:
    client = _build_app(admin_token="t0k3n")
    response = client.get(
        "/v1/admin/agents",
        headers={"Authorization": "Bearer nope"},
    )
    assert response.status_code == 401


def test_agents_returns_503_when_token_unset() -> None:
    client = _build_app(admin_token=None)
    response = client.get(
        "/v1/admin/agents",
        headers={"Authorization": "Bearer anything"},
    )
    assert response.status_code == 503


def test_agents_lists_tenants_with_valid_bearer() -> None:
    tenant = _make_tenant()
    client = _build_app(admin_token="t0k3n", tenants=[tenant])
    response = client.get(
        "/v1/admin/agents",
        headers={"Authorization": "Bearer t0k3n"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["agents"]) == 1
    assert body["agents"][0]["tenant_name"] == "acme"
    assert body["agents"][0]["ens_name"] == "support.acme.eth"


def test_audit_returns_401_without_bearer() -> None:
    client = _build_app(admin_token="t0k3n")
    response = client.get(f"/v1/admin/audit/{uuid4()}")
    assert response.status_code == 401


def test_audit_returns_entries() -> None:
    tenant_id = uuid4()
    pair = _make_receipt_pair(tenant_id)
    client = _build_app(admin_token="t0k3n", pairs=[pair])
    response = client.get(
        f"/v1/admin/audit/{tenant_id}",
        headers={"Authorization": "Bearer t0k3n"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tenant_id"] == str(tenant_id)
    assert len(body["entries"]) == 1
    entry = body["entries"][0]
    assert entry["model_id"] == "echo-llm"
    assert entry["tools_used"] == ["rag_search"]
    assert entry["retrieval_ids"] == ["h1", "h2"]


def test_audit_rejects_bad_limit() -> None:
    client = _build_app(admin_token="t0k3n")
    response = client.get(
        f"/v1/admin/audit/{uuid4()}?limit=0",
        headers={"Authorization": "Bearer t0k3n"},
    )
    assert response.status_code == 400


def test_healthz_returns_detail() -> None:
    now = datetime.now(UTC)
    result = TaskResult(
        name="healthcheck_upstreams",
        started_at=now,
        finished_at=now,
        success=True,
        summary="ok",
        details={"services": {"database": {"status": "up"}}},
    )
    client = _build_app(admin_token="t0k3n", healthcheck_result=result)
    response = client.get(
        "/v1/admin/healthz",
        headers={"Authorization": "Bearer t0k3n"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["services"]["database"]["status"] == "up"


def test_healthz_requires_bearer() -> None:
    client = _build_app(admin_token="t0k3n")
    response = client.get("/v1/admin/healthz")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_require_admin_bearer_passes_through_dependency_chain() -> None:
    """Smoke test the constant-time path runs at request handling time."""
    client = _build_app(admin_token="abc")
    response = client.get(
        "/v1/admin/agents",
        headers={"Authorization": "Bearer abc"},
    )
    assert response.status_code == 200
    # the dependency itself is a no-op for callers (raises on failure)
    _ = require_admin_bearer
