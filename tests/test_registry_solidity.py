"""Optional sanity check that ``AegisRegistry.sol`` parses.

This is NOT a CI-required test. It runs only when:

* ``py-solc-x`` is importable (the ``contracts`` extra is installed).
* solc 0.8.24 is already cached locally so we do NOT trigger a network
  download — CLAUDE.md §3 forbids non-integration tests from doing so.

If either condition is false we skip cleanly. Live deploy tests
belong behind ``@pytest.mark.integration`` (none here).
"""

from __future__ import annotations

from pathlib import Path

import pytest

_SOLC_VERSION = "0.8.24"
_SOURCE = Path("contracts") / "AegisRegistry.sol"


def test_aegis_registry_sol_parses() -> None:
    solcx = pytest.importorskip("solcx")
    if not _SOURCE.exists():
        pytest.skip("contracts/AegisRegistry.sol missing")

    installed = [str(v) for v in solcx.get_installed_solc_versions()]
    if _SOLC_VERSION not in installed:
        pytest.skip(f"solc {_SOLC_VERSION} not cached locally; skipping (no auto-download).")

    solcx.set_solc_version(_SOLC_VERSION)
    source = _SOURCE.read_text(encoding="utf-8")
    compiled = solcx.compile_source(source, output_values=["abi", "bin"])
    keys = list(compiled)
    assert any(k.endswith(":AegisRegistry") for k in keys), keys
