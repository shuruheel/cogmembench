from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ..substrate import EvidenceMode, SubstrateAdapter
from .adapter_contract import validate_adapter_contract


def audit_adapter_portability(adapter: SubstrateAdapter) -> dict[str, Any]:
    """Compare declared v2 capabilities with mechanically observed behavior."""
    manifest = adapter.capability_manifest()
    try:
        contract = validate_adapter_contract(adapter)
        infrastructure_error = None
    except Exception as exc:
        contract = {"passed": False, "checks": {}}
        infrastructure_error = f"{type(exc).__name__}: {exc}"
    checks = contract.get("checks", {})

    def status(declared: bool, check: str) -> str:
        if not declared:
            return "capability_absent"
        if infrastructure_error:
            return "infrastructure_failure"
        return "present_correct" if checks.get(check, False) else "present_incorrect"

    coverage = {
        "snapshot": status(manifest.snapshot, "dual_axis_snapshot"),
        "audit_export": status(manifest.audit_export, "decision_time_audit"),
        "automatic_capture": status(manifest.automatic_capture, "automatic_capture"),
        "revision": status(manifest.revision, "dual_axis_snapshot"),
        "relations": status(manifest.relations, "relation_round_trip"),
        "reset": status(True, "verified_reset"),
        "namespace_isolation": status(True, "namespace_isolation"),
        "usage_reporting": status(True, "explicit_usage_fidelity"),
    }
    evidence_admissible = manifest.evidence_mode is not EvidenceMode.SIDECAR
    return {
        "adapter": manifest.adapter_name,
        "adapter_version": manifest.adapter_version,
        "manifest": asdict(manifest),
        "contract": contract,
        "coverage": coverage,
        "evidence_admissible": evidence_admissible,
        "infrastructure_error": infrastructure_error,
        "passed": bool(contract.get("passed")) and evidence_admissible,
    }
