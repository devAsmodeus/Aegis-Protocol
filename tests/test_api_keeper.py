"""Unit tests for the ``/v1/keeper`` router.

Uses FastAPI's TestClient with a dedicated app per test so the
keeper-registry dependency override is isolated. No real DB / Redis /
RPC. Settings are overridden via the ``get_settings`` dependency to
inject a test-only signing secret.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest
from aegis.api.dependencies import get_keeper_registry
from aegis.config import Settings, get_settings
from aegis.keeper import KeeperRegistry, TaskResult
from aegis.main import create_app
from fastapi.testclient import TestClient


@dataclass(slots=True)
class _StubTask:
    name: str = "alpha"
    runs: int = field(default=0)

    async def run(self) -> TaskResult:
        self.runs += 1
        now = datetime.now(UTC)
        return TaskResult(
            name=self.name,
            started_at=now,
            finished_at=now,
            success=True,
            summary="ok",
            details={"runs": self.runs},
        )


def _build_app(*, secret: str | None) -> tuple[TestClient, _StubTask]:
    app = create_app()
    task = _StubTask(name="alpha")
    registry = KeeperRegistry()
    registry.register(task)

    def _override_registry() -> KeeperRegistry:
        return registry

    def _override_settings() -> Settings:
        return Settings(keeper_signing_secret=secret)

    app.dependency_overrides[get_keeper_registry] = _override_registry
    app.dependency_overrides[get_settings] = _override_settings
    return TestClient(app), task


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_list_tasks_no_auth_returns_names() -> None:
    client, _ = _build_app(secret="secret")
    response = client.get("/v1/keeper/tasks")
    assert response.status_code == 200
    assert response.json() == {"tasks": ["alpha"]}


def test_run_task_returns_503_without_configured_secret() -> None:
    client, _ = _build_app(secret=None)
    response = client.post("/v1/keeper/tasks/alpha/run", content=b"{}")
    assert response.status_code == 503


def test_run_task_returns_401_without_signature() -> None:
    client, _ = _build_app(secret="secret")
    response = client.post("/v1/keeper/tasks/alpha/run", content=b"{}")
    assert response.status_code == 401


def test_run_task_returns_401_with_bad_signature() -> None:
    client, _ = _build_app(secret="secret")
    response = client.post(
        "/v1/keeper/tasks/alpha/run",
        content=b"{}",
        headers={"X-Aegis-Keeper-Signature": "deadbeef"},
    )
    assert response.status_code == 401


def test_run_task_runs_with_valid_signature() -> None:
    client, task = _build_app(secret="secret")
    body = json.dumps({"trigger": "manual"}).encode("utf-8")
    sig = _sign("secret", body)
    response = client.post(
        "/v1/keeper/tasks/alpha/run",
        content=body,
        headers={"X-Aegis-Keeper-Signature": sig},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["name"] == "alpha"
    assert payload["success"] is True
    assert task.runs == 1


def test_run_task_unknown_returns_404() -> None:
    client, _ = _build_app(secret="secret")
    body = b""
    sig = _sign("secret", body)
    response = client.post(
        "/v1/keeper/tasks/missing/run",
        content=body,
        headers={"X-Aegis-Keeper-Signature": sig},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_run_task_signature_must_match_full_body() -> None:
    """A signature for a different body must be rejected."""
    client, _ = _build_app(secret="secret")
    real_body = b'{"a":1}'
    other_body = b'{"a":2}'
    sig_for_other = _sign("secret", other_body)
    response = client.post(
        "/v1/keeper/tasks/alpha/run",
        content=real_body,
        headers={"X-Aegis-Keeper-Signature": sig_for_other},
    )
    assert response.status_code == 401
