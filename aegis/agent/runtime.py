"""Async tool-loop runtime.

Implements the observe → decide → act loop that turns an
:class:`AgentRequest` into an :class:`AgentResponse` and a
content-hashed :class:`ReceiptDraft`.

Pseudocode::

    messages = build_initial_messages(request)
    for _ in range(max_tool_calls + 1):
        out = await llm.complete(messages, tools)
        if out.text:
            return finalize(out)
        for call in out.tool_calls:
            result = await dispatch(call)
            messages.append(tool_result_message(result))
    return budget_exhausted_response()
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from aegis.agent.errors import UnknownToolError
from aegis.agent.protocol import LLMClient, ReceiptSink, Tool
from aegis.agent.types import (
    AgentRequest,
    AgentResponse,
    LLMOutput,
    ReceiptDraft,
    ToolResult,
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class Runtime:
    """Bounded async tool-loop runtime.

    Attributes:
        llm: LLM client (real or stub).
        tools: Tool registry. Indexed by ``name`` on construction.
        receipt_sink: Persists a receipt for each completed run.
        max_tool_calls: Hard cap on tool dispatch per run. Reaching it
            short-circuits with ``"(tool budget exhausted)"`` and still
            records a receipt.
        system_prompt: Optional system message prepended to the LLM
            history. Empty by default so tests need not override.
    """

    llm: LLMClient
    tools: Sequence[Tool]
    receipt_sink: ReceiptSink
    max_tool_calls: int = 4
    system_prompt: str = ""
    _registry: dict[str, Tool] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self._registry = {t.name: t for t in self.tools}

    async def run(self, request: AgentRequest) -> AgentResponse:
        messages: list[dict[str, Any]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": request.text})

        retrieval_hashes: list[str] = []
        tools_used: list[str] = []
        budget = self.max_tool_calls

        while True:
            output: LLMOutput = await self.llm.complete(messages, self.tools)

            if output.tool_calls:
                if budget <= 0:
                    final_text = "(tool budget exhausted)"
                    return await self._finalize(
                        request=request,
                        text=final_text,
                        retrieval_hashes=retrieval_hashes,
                        tools_used=tools_used,
                    )
                for call in output.tool_calls:
                    tool = self._registry.get(call.name)
                    if tool is None:
                        raise UnknownToolError(call.name)
                    result = await tool.call(dict(call.arguments))
                    tools_used.append(result.name)
                    retrieval_hashes.extend(self._extract_hashes(result.metadata))
                    messages.append(self._tool_result_to_message(result))
                    budget -= 1
                continue

            return await self._finalize(
                request=request,
                text=output.text,
                retrieval_hashes=retrieval_hashes,
                tools_used=tools_used,
            )

    async def _finalize(
        self,
        *,
        request: AgentRequest,
        text: str,
        retrieval_hashes: list[str],
        tools_used: list[str],
    ) -> AgentResponse:
        deduped_hashes = tuple(dict.fromkeys(retrieval_hashes))
        tools_tuple = tuple(tools_used)
        response = AgentResponse(
            text=text,
            retrieval_hashes=deduped_hashes,
            tools_used=tools_tuple,
            model_id=self.llm.model_id,
        )
        draft = ReceiptDraft(
            tenant_id=request.tenant_id,
            conversation_id=request.conversation_id,
            input_hash=_sha256(request.text),
            output_hash=_sha256(text),
            model_id=self.llm.model_id,
            retrieval_hashes=deduped_hashes,
            tools_used=tools_tuple,
            payload={
                "external_user_id": request.external_user_id,
            },
        )
        await self.receipt_sink.record(draft)
        return response

    @staticmethod
    def _extract_hashes(metadata: Mapping[str, Any]) -> list[str]:
        raw = metadata.get("content_hashes")
        if not raw:
            return []
        return [str(h) for h in raw]

    @staticmethod
    def _tool_result_to_message(result: ToolResult) -> dict[str, Any]:
        return {"role": "tool", "name": result.name, "content": result.output}
