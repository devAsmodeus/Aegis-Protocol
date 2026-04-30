"""Smoke tests for the frozen dataclasses in :mod:`aegis.agent.types`."""

from __future__ import annotations

import dataclasses
from uuid import uuid4

import pytest
from aegis.agent.types import (
    AgentRequest,
    AgentResponse,
    LLMOutput,
    ReceiptDraft,
    ToolCall,
    ToolResult,
)


def test_agent_request_defaults() -> None:
    req = AgentRequest(text="hi")

    assert req.text == "hi"
    assert req.tenant_id is None
    assert req.conversation_id is None
    assert req.external_user_id is None


def test_agent_request_is_frozen() -> None:
    req = AgentRequest(text="hi")

    with pytest.raises(dataclasses.FrozenInstanceError):
        req.text = "bye"  # type: ignore[misc]


def test_agent_response_holds_traceability_fields() -> None:
    resp = AgentResponse(
        text="ok",
        retrieval_hashes=("h1", "h2"),
        tools_used=("rag_search",),
        model_id="echo",
    )

    assert resp.text == "ok"
    assert resp.retrieval_hashes == ("h1", "h2")
    assert resp.tools_used == ("rag_search",)
    assert resp.model_id == "echo"


def test_tool_call_default_arguments_independent_per_instance() -> None:
    a = ToolCall(name="t")
    b = ToolCall(name="t")

    assert a.arguments == {}
    assert b.arguments == {}
    assert a.arguments is not b.arguments


def test_tool_result_round_trip() -> None:
    tr = ToolResult(name="t", output="x", metadata={"k": "v"})

    assert (tr.name, tr.output, tr.metadata) == ("t", "x", {"k": "v"})


def test_llm_output_defaults_to_empty_text_and_no_tool_calls() -> None:
    out = LLMOutput()

    assert out.text == ""
    assert out.tool_calls == ()


def test_receipt_draft_holds_all_required_fields() -> None:
    cid = uuid4()
    draft = ReceiptDraft(
        tenant_id="t1",
        conversation_id=cid,
        input_hash="abc",
        output_hash="def",
        model_id="echo",
        retrieval_hashes=("h1",),
        tools_used=("rag_search",),
        payload={"foo": "bar"},
    )

    assert draft.tenant_id == "t1"
    assert draft.conversation_id == cid
    assert draft.input_hash == "abc"
    assert draft.output_hash == "def"
    assert draft.model_id == "echo"
    assert draft.retrieval_hashes == ("h1",)
    assert draft.tools_used == ("rag_search",)
    assert draft.payload == {"foo": "bar"}
