"""Smoke test for ``scripts.demo_walkthrough``.

Runs the demo end-to-end through stubs only (no docker, no network)
and asserts the captured outcomes. Acts as a regression guard so the
demo never silently breaks before submission.
"""

from __future__ import annotations

import pytest
from scripts.demo_walkthrough import run_demo


@pytest.mark.asyncio
async def test_run_demo_completes_with_expected_outcomes() -> None:
    summary = await run_demo()
    assert summary["registry_active"] is True
    assert "Treat unlimited token allowances" in str(summary["agent_text"])
    assert summary["tools_used"] == ["rag_search"]
    assert isinstance(summary["receipt_input_hash"], str)
    assert len(str(summary["receipt_input_hash"])) == 64
    assert len(str(summary["receipt_output_hash"])) == 64
    assert summary["keeper_summary"] == "ok"
