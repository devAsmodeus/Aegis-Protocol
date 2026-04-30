"""``rag_search`` tool: retrieves chunks via :class:`RagService`.

The tool's ``output`` is a newline-joined snippet of the top-`k` hits
so the LLM can quote it. The hit content-hashes are surfaced in
``ToolResult.metadata["content_hashes"]`` so the runtime can roll them
into the receipt without re-running the query.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aegis.agent.types import ToolResult
from aegis.rag.service import RagService


@dataclass(slots=True)
class RagSearchTool:
    """Wraps :class:`RagService` as a runtime-callable tool."""

    service: RagService
    top_k: int = 4
    name: str = field(default="rag_search", init=False)
    description: str = field(
        default=(
            "Search the project's knowledge base for relevant snippets. "
            "Use when the user asks about documentation, on-chain protocol "
            "details, or anything not present in the conversation."
        ),
        init=False,
    )

    @property
    def json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural-language query to search for.",
                },
                "tenant_id": {
                    "type": "string",
                    "description": "Optional tenant scope override.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        }

    async def call(self, arguments: dict[str, Any]) -> ToolResult:
        query = str(arguments["query"])
        tenant_id = arguments.get("tenant_id")
        hits = await self.service.search(
            text=query,
            tenant_id=tenant_id if isinstance(tenant_id, str) else None,
            k=self.top_k,
        )
        joined = "\n\n".join(h.content for h in hits)
        return ToolResult(
            name=self.name,
            output=joined,
            metadata={
                "content_hashes": tuple(h.content_hash for h in hits),
                "sources": tuple(h.source for h in hits),
            },
        )
