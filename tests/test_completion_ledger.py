from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_completion_ledger_is_exhaustive_and_uses_declared_statuses() -> None:
    ledger = json.loads((ROOT / "configs" / "cognitive_v2_completion.json").read_text())
    statuses = set(ledger["status_definitions"])

    assert set(ledger["phases"]) == set("ABCDEFGH")
    assert set(ledger["gates"]) == {str(value) for value in range(9)}
    assert ledger["credential_free_rehearsal"]["scenario_count"] == 450
    assert ledger["credential_free_rehearsal"]["release_contamination_audit_passed"]
    assert (ROOT / ledger["credential_free_rehearsal"]["evidence"]).exists()

    observed = set()
    for phase in ledger["phases"].values():
        observed.add(phase["implementation_status"])
        observed.add(phase["exit_status"])
        observed.update(phase["deliverables"].values())
    observed.update(gate["status"] for gate in ledger["gates"].values())
    assert observed <= statuses


def test_package_and_dataset_license_declarations_exist() -> None:
    assert "Apache License" in (ROOT / "LICENSE").read_text()
    assert "Creative Commons Attribution 4.0" in (ROOT / "DATA_LICENSE.md").read_text()
