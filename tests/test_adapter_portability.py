from __future__ import annotations

from cogmembench.substrate import FlatSubstrateAdapter, ReferenceSubstrateAdapter
from cogmembench.validation import audit_adapter_portability


def test_portability_audit_distinguishes_absent_audit_capability() -> None:
    result = audit_adapter_portability(FlatSubstrateAdapter())

    assert result["passed"]
    assert result["coverage"]["audit_export"] == "capability_absent"
    assert result["coverage"]["snapshot"] == "present_correct"


def test_portability_audit_accepts_native_reference_evidence() -> None:
    result = audit_adapter_portability(ReferenceSubstrateAdapter())

    assert result["passed"]
    assert result["evidence_admissible"]
    assert result["coverage"]["audit_export"] == "present_correct"
