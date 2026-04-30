"""Tests for canonical content-hash and frozen dataclasses."""

from __future__ import annotations

import hashlib

import pytest
from aegis.retrieval import RetrievalHit, RetrievalQuery, content_hash


def test_content_hash_is_sha256_hex_of_utf8() -> None:
    text = "The quick brown fox jumps over the lazy dog"
    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert content_hash(text) == expected


def test_content_hash_stable_across_calls() -> None:
    assert content_hash("aegis") == content_hash("aegis")


def test_content_hash_distinguishes_whitespace() -> None:
    assert content_hash("a b") != content_hash("a  b")


def test_content_hash_handles_unicode() -> None:
    text = "Привет, мир — 🚀"
    digest = content_hash(text)
    assert len(digest) == 64
    assert digest == hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_retrieval_query_is_frozen() -> None:
    q = RetrievalQuery(text="hi")
    with pytest.raises((AttributeError, TypeError)):
        q.text = "no"  # type: ignore[misc]


def test_retrieval_hit_is_frozen() -> None:
    h = RetrievalHit(content="x", content_hash=content_hash("x"), score=1.0, source="t")
    with pytest.raises((AttributeError, TypeError)):
        h.score = 2.0  # type: ignore[misc]
