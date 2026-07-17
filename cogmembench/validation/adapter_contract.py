from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ..substrate import (
    ArtifactKind,
    CognitiveArtifact,
    EpistemicStatus,
    RelationKind,
    RetrievalBudget,
    SubstrateAdapter,
    TimeInterval,
    UsageFidelity,
)
from ..scenarios.schema import Event


def _artifact(
    namespace: str,
    artifact_id: str,
    kind: ArtifactKind,
    content: str,
    valid_start: int,
    **changes: Any,
) -> CognitiveArtifact:
    return CognitiveArtifact(
        artifact_id=artifact_id,
        kind=kind,
        content=content,
        scenario_id=namespace,
        valid_time=TimeInterval(valid_start),
        epistemic_status=EpistemicStatus.ACCEPTED,
        **changes,
    )


def validate_adapter_contract(adapter: SubstrateAdapter) -> dict[str, Any]:
    """Run the generic, deterministic adapter-v2 behavioral contract."""
    namespace = "adapter-contract-v2"
    checks: dict[str, bool] = {}
    adapter.reset(namespace)
    adapter.quiesce()
    manifest = adapter.capability_manifest()

    observed = adapter.observe(
        Event(
            "contract-session",
            1,
            "user",
            "automatic capture sentinel",
            event_time=5,
            report_time=9,
            event_id="automatic-event",
            phase="accumulate",
        ),
        9,
    )
    checks["automatic_capture"] = (
        observed.content == "automatic capture sentinel"
        and observed.scenario_id == namespace
        and "automatic-event" in observed.provenance_event_ids
    )

    evidence = _artifact(
        namespace,
        "evidence-old",
        ArtifactKind.EVIDENCE,
        "provisional alpha limit 100",
        5,
    )
    claim = _artifact(
        namespace,
        "claim-old",
        ArtifactKind.CLAIM,
        "alpha limit is 100",
        5,
    )
    stored_evidence = adapter.commit(evidence, 10)
    stored_claim = adapter.commit(claim, 10)
    repeated_claim = adapter.commit(claim, 10)
    checks["idempotent_commit"] = stored_claim == repeated_claim
    support_relation = adapter.link(
        stored_evidence.artifact_id,
        RelationKind.SUPPORTS,
        stored_claim.artifact_id,
        10,
    )
    retrieval = adapter.retrieve("alpha limit", RetrievalBudget(2), 11)
    checks["bounded_retrieval"] = 0 < len(retrieval.items) <= 2 and all(
        item.artifact.scenario_id == namespace for item in retrieval.items
    )

    decision = _artifact(
        namespace,
        "decision",
        ArtifactKind.DECISION,
        "configure alpha at 90",
        12,
        structured_content={
            "retrieved_artifact_ids": [item.artifact.artifact_id for item in retrieval.items]
        },
    )
    stored_decision = adapter.commit(decision, 12)
    adapter.link(
        stored_claim.artifact_id,
        RelationKind.SUPPORTS,
        stored_decision.artifact_id,
        12,
    )

    corrected_claim = _artifact(
        namespace,
        "claim-new",
        ArtifactKind.CLAIM,
        "alpha limit is 240",
        5,
    )
    adapter.revise(stored_claim.artifact_id, corrected_claim, 20)
    historical = adapter.snapshot(valid_at=5, known_at=15)
    current = adapter.snapshot(valid_at=5, known_at=20)
    historical_ids = {artifact.artifact_id for artifact in historical.artifacts}
    current_ids = {artifact.artifact_id for artifact in current.artifacts}
    checks["dual_axis_snapshot"] = (
        stored_claim.artifact_id in historical_ids
        and corrected_claim.artifact_id not in historical_ids
        and corrected_claim.artifact_id in current_ids
        and stored_claim.artifact_id not in current_ids
    )
    checks["relation_round_trip"] = support_relation.relation_id in {
        relation.relation_id for relation in historical.relations
    }

    if manifest.audit_export:
        receipt = adapter.export_audit(stored_decision.artifact_id)
        checks["decision_time_audit"] = (
            stored_claim.artifact_id in receipt.evidence_ids
            and corrected_claim.artifact_id not in receipt.evidence_ids
        )
    else:
        checks["decision_time_audit"] = True

    adapter.close_session("contract-session", 20)
    adapter.quiesce()
    usage = adapter.usage_report()
    checks["explicit_usage_fidelity"] = usage.fidelity is not UsageFidelity.UNAVAILABLE or bool(
        usage.reason
    )
    usage_payload = asdict(usage)
    usage_payload["fidelity"] = usage.fidelity.value

    adapter.reset(namespace)
    adapter.quiesce()
    empty = adapter.snapshot()
    contamination = adapter.retrieve("alpha limit 100 240", RetrievalBudget(5), 0)
    checks["verified_reset"] = not empty.artifacts and not contamination.items
    checks["namespace_isolation"] = all(
        artifact.scenario_id == namespace for artifact in empty.artifacts
    )
    return {
        "adapter": manifest.adapter_name,
        "adapter_version": manifest.adapter_version,
        "clock_mode": manifest.clock_mode.value,
        "usage_fidelity": manifest.usage_fidelity.value,
        "usage": usage_payload,
        "checks": checks,
        "passed": all(checks.values()),
    }
