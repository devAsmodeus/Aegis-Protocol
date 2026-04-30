"""Schema-only assertions: validates ORM metadata without a live DB."""

from __future__ import annotations

from aegis.db import models as _models  # noqa: F401  -- registers tables on Base.metadata
from aegis.db.base import Base


def test_all_tables_present() -> None:
    expected = {"tenants", "conversations", "messages", "receipts"}
    assert expected.issubset(set(Base.metadata.tables.keys()))


def test_tenant_ens_columns_are_nullable() -> None:
    tenants = Base.metadata.tables["tenants"]
    assert tenants.c.ens_name.nullable is True
    assert tenants.c.registry_addr.nullable is True


def test_foreign_keys_target_correct_tables() -> None:
    conversations = Base.metadata.tables["conversations"]
    messages = Base.metadata.tables["messages"]
    receipts = Base.metadata.tables["receipts"]

    tenant_fks = {fk.target_fullname for fk in conversations.c.tenant_id.foreign_keys}
    assert "tenants.id" in tenant_fks

    conv_fks = {fk.target_fullname for fk in messages.c.conversation_id.foreign_keys}
    assert "conversations.id" in conv_fks

    msg_fks = {fk.target_fullname for fk in receipts.c.message_id.foreign_keys}
    assert "messages.id" in msg_fks


def test_receipt_message_id_is_unique() -> None:
    receipts = Base.metadata.tables["receipts"]
    assert receipts.c.message_id.unique is True


def test_receipt_jsonb_columns_are_not_null() -> None:
    receipts = Base.metadata.tables["receipts"]
    for col_name in ("retrieval_ids", "tools_used", "payload_json"):
        assert receipts.c[col_name].nullable is False
