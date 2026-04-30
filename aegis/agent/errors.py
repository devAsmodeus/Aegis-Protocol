"""Agent-runtime exceptions."""

from __future__ import annotations


class AgentRuntimeError(Exception):
    """Base class for runtime errors raised by :mod:`aegis.agent`."""


class UnknownToolError(AgentRuntimeError):
    """Raised when the LLM requests a tool the runtime does not know."""

    def __init__(self, name: str) -> None:
        super().__init__(f"unknown tool: {name!r}")
        self.name = name
