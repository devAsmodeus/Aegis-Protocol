"""Unit tests for :func:`aegis.chain.registry.load_deployment`."""

from __future__ import annotations

import json
from pathlib import Path

from aegis.chain.registry import load_deployment


def test_load_deployment_missing_returns_none(tmp_path: Path) -> None:
    assert load_deployment(99999, base_dir=tmp_path) is None


def test_load_deployment_reads_json(tmp_path: Path) -> None:
    payload = {
        "address": "0x000000000000000000000000000000000000abcd",
        "abi": [{"type": "function", "name": "isActive"}],
        "deployedAt": "2026-05-02T00:00:00+00:00",
        "deployedBy": "0x000000000000000000000000000000000000aaaa",
    }
    (tmp_path / "16601.json").write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_deployment(16601, base_dir=tmp_path)
    assert loaded == payload
