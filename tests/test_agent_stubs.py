"""Unit tests for `aegis.agent.stubs`."""

from __future__ import annotations

import pytest
from aegis.agent.stubs import EchoLLM, StaticToolPlanLLM
from aegis.agent.types import ToolCall


@pytest.mark.asyncio
async def test_echo_llm_returns_last_user_message() -> None:
    llm = EchoLLM()
    messages = [
        {"role": "system", "content": "you are a helper"},
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "second"},
    ]

    out = await llm.complete(messages, [])

    assert out.text == "second"
    assert out.tool_calls == ()
    assert llm.model_id == "echo-llm"


@pytest.mark.asyncio
async def test_echo_llm_no_user_messages_returns_empty() -> None:
    out = await EchoLLM().complete([{"role": "system", "content": "x"}], [])

    assert out.text == ""


@pytest.mark.asyncio
async def test_static_plan_llm_walks_plan_in_order() -> None:
    plan: list[ToolCall | str] = [
        ToolCall(name="rag_search", arguments={"query": "x"}),
        "final reply",
    ]
    llm = StaticToolPlanLLM(plan=plan)

    first = await llm.complete([], [])
    second = await llm.complete([], [])
    third = await llm.complete([], [])

    assert first.tool_calls == (ToolCall(name="rag_search", arguments={"query": "x"}),)
    assert first.text == ""
    assert second.text == "final reply"
    assert second.tool_calls == ()
    # exhausted plan: empty output (loop will break out).
    assert third.text == ""
    assert third.tool_calls == ()
