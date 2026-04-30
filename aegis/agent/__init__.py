"""Agent runtime: observe → decide → act tool-loop.

The agent runtime turns a user message + tenant context into a verified
response. It composes:

* an :class:`~aegis.agent.protocol.LLMClient` (cloud or stubbed) that
  produces either a final text reply or a tool call,
* a registry of :class:`~aegis.agent.protocol.Tool` instances (RAG
  search, on-chain tools later, …),
* a :class:`~aegis.agent.protocol.ReceiptSink` that records a
  content-hash receipt for every reply (per ``CLAUDE.md`` §3).

The loop is async-first and bounded by ``max_tool_calls`` so a
mis-behaving model cannot fan out indefinitely.
"""
