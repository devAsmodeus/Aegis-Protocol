"""Concrete tools the runtime can invoke.

Tools conform to :class:`aegis.agent.protocol.Tool`. Each tool lives in
its own module so they can be added/removed without churning a single
megafile.
"""

from aegis.agent.tools.rag import RagSearchTool

__all__ = ["RagSearchTool"]
