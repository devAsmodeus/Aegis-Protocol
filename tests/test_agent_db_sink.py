"""Unit tests for `aegis.agent.db_sink.SqlReceiptSink`.

We don't bring up Postgres here — we inject a fake `async_sessionmaker`
that records the `add`/`commit` sequence. Real DB exercise is left to
the integration suite.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from aegis.agent.db_sink import SqlReceiptSink
from aegis.agent.types import ReceiptDraft
from aegis.db.models import Receipt


class _FakeSession:
    def __init__(self, log: list[tuple[str, Any]]) -> None:
        self._log = log

    async def __aenter__(self) -> _FakeSession:
        self._log.append(("enter", None))
        return self

    async def __aexit__(self, *exc: Any) -> None:
        self._log.append(("exit", None))

    def add(self, obj: Any) -> None:
        self._log.append(("add", obj))

    async def commit(self) -> None:
        self._log.append(("commit", None))


def _factory(log: list[tuple[str, Any]]):
    def _build() -> _FakeSession:
        return _FakeSession(log)

    return _build


def _draft(**overrides: Any) -> ReceiptDraft:
    base = {
        "tenant_id": "t1",
        "conversation_id": uuid4(),
        "input_hash": "i" * 64,
        "output_hash": "o" * 64,
        "model_id": "echo-llm",
        "retrieval_hashes": ("h1", "h2"),
        "tools_used": ("rag_search",),
        "payload": {"external_user_id": "u1"},
    }
    base.update(overrides)
    return ReceiptDraft(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_sink_no_message_id_provider_is_noop() -> None:
    """Without a `message_id_provider`, the sink silently no-ops; the
    runtime can still run before message persistence lands."""
    log: list[tuple[str, Any]] = []
    sink = SqlReceiptSink(session_factory=_factory(log))  # type: ignore[arg-type]

    await sink.record(_draft())

    assert log == []


@pytest.mark.asyncio
async def test_sink_persists_receipt_with_provider() -> None:
    log: list[tuple[str, Any]] = []
    msg_id = uuid4()
    sink = SqlReceiptSink(
        session_factory=_factory(log),  # type: ignore[arg-type]
        message_id_provider=lambda _draft: msg_id,
    )

    await sink.record(_draft())

    actions = [name for name, _ in log]
    assert actions == ["enter", "add", "commit", "exit"]
    added: Receipt = next(obj for name, obj in log if name == "add")
    assert isinstance(added, Receipt)
    assert added.message_id == msg_id
    assert added.input_hash == "i" * 64
    assert added.output_hash == "o" * 64
    assert added.model_id == "echo-llm"
    assert added.retrieval_ids == ["h1", "h2"]
    assert added.tools_used == ["rag_search"]
    assert added.payload_json == {"external_user_id": "u1"}


@pytest.mark.asyncio
async def test_sink_provider_returning_non_uuid_skips_write() -> None:
    log: list[tuple[str, Any]] = []
    sink = SqlReceiptSink(
        session_factory=_factory(log),  # type: ignore[arg-type]
        message_id_provider=lambda _draft: "not-a-uuid",
    )

    await sink.record(_draft())

    assert log == []


def test_uuid_roundtrip_through_provider() -> None:
    """Sanity: ensure the helper signature stays UUID-typed."""
    val: UUID = uuid4()
    sink = SqlReceiptSink(
        session_factory=lambda: None,  # type: ignore[arg-type]
        message_id_provider=lambda _draft: val,
    )
    resolved = sink._resolve_message_id(_draft())
    assert resolved == val
