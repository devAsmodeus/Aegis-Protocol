"""RAG service layer.

Tenant-scoped public API on top of :mod:`aegis.retrieval`. The retrieval
package implements the low-level hybrid pipeline (dense + BM25 + RRF +
optional reranker); this package wraps it in a small service object that
the agent runtime calls during a tool invocation.
"""
