"""``/v1/admin`` router — read-only admin surface.

Endpoints (all bearer-auth via :func:`require_admin_bearer`):

* ``GET /v1/admin/agents`` — list agent records. Day 8 schema does not
  yet ship a dedicated ``agents`` table, so this proxies the
  :class:`Tenant` rows extended with the ENS / registry-address columns
  that the registry uses to identify agents. Once a dedicated
  ``agents`` table lands the response shape stays identical (Pydantic
  ``AgentRow``).
* ``GET /v1/admin/audit/{tenant_id}`` — last N receipts for a tenant
  (joined through ``messages`` → ``conversations``). Day 8 schema uses
  ``receipts`` as the audit log; the route shape will not change when a
  dedicated ``audit_log`` table is added in a follow-up migration.
* ``GET /v1/admin/healthz`` — runs
  :class:`HealthcheckUpstreamsTask` and surfaces the per-service
  detail.

Why we route through tenants/receipts: Day 2 didn't ship an ``agents``
or ``audit_log`` table; only ``tenants``, ``conversations``,
``messages``, ``receipts`` exist. Adding new tables in PR #3 would
require a migration on top of `001_init`, expanding scope. The route
contracts are designed so the migration can be additive when it lands.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from aegis.api.dependencies import (
    DbSessionDep,
    KeeperRegistryDep,
    require_admin_bearer,
)
from aegis.db.models import Conversation, Message, Receipt, Tenant

router = APIRouter(
    prefix="/v1/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_bearer)],
)


class AgentRow(BaseModel):
    """One row of ``GET /v1/admin/agents``.

    Mirrors the columns a future dedicated ``agents`` table would hold;
    today these are read off the ``tenants`` row.
    """

    id: UUID
    tenant_name: str
    ens_name: str | None
    registry_addr: str | None


class AgentList(BaseModel):
    """Response payload for ``GET /v1/admin/agents``."""

    agents: list[AgentRow]


class AuditEntry(BaseModel):
    """One row of ``GET /v1/admin/audit/{tenant_id}``."""

    receipt_id: UUID
    message_id: UUID
    conversation_id: UUID
    input_hash: str
    output_hash: str
    model_id: str
    tools_used: list[str]
    retrieval_ids: list[str]


class AuditPage(BaseModel):
    """Response payload for ``GET /v1/admin/audit/{tenant_id}``."""

    tenant_id: UUID
    entries: list[AuditEntry]


class HealthDetail(BaseModel):
    """Response payload for ``GET /v1/admin/healthz``."""

    success: bool
    summary: str
    services: dict[str, dict[str, Any]] = Field(default_factory=dict)


@router.get("/agents", response_model=AgentList)
async def list_agents(session: DbSessionDep) -> AgentList:
    """List agent records (proxied from ``tenants``)."""
    result = await session.execute(select(Tenant).order_by(Tenant.created_at))
    rows = result.scalars().all()
    return AgentList(
        agents=[
            AgentRow(
                id=row.id,
                tenant_name=row.name,
                ens_name=row.ens_name,
                registry_addr=row.registry_addr,
            )
            for row in rows
        ]
    )


@router.get("/audit/{tenant_id}", response_model=AuditPage)
async def get_audit(
    tenant_id: UUID,
    session: DbSessionDep,
    limit: int = 50,
) -> AuditPage:
    """Return the last ``limit`` receipts for the given tenant."""
    if limit <= 0 or limit > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit must be between 1 and 500",
        )
    stmt = (
        select(Receipt, Message)
        .join(Message, Receipt.message_id == Message.id)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.tenant_id == tenant_id)
        .order_by(Receipt.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    pairs = result.all()
    entries = [
        AuditEntry(
            receipt_id=receipt.id,
            message_id=message.id,
            conversation_id=message.conversation_id,
            input_hash=receipt.input_hash,
            output_hash=receipt.output_hash,
            model_id=receipt.model_id,
            tools_used=list(receipt.tools_used),
            retrieval_ids=list(receipt.retrieval_ids),
        )
        for receipt, message in pairs
    ]
    return AuditPage(tenant_id=tenant_id, entries=entries)


@router.get("/healthz", response_model=HealthDetail)
async def healthz(registry: KeeperRegistryDep) -> HealthDetail:
    """Run the upstream healthcheck and return per-service status."""
    task = registry.get("healthcheck_upstreams")
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="healthcheck_upstreams task not registered",
        )
    result = await task.run()
    services_obj = result.details.get("services", {})
    services = services_obj if isinstance(services_obj, dict) else {}
    return HealthDetail(
        success=result.success,
        summary=result.summary,
        services=services,
    )


__all__ = ["router"]
