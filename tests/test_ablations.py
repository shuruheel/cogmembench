from __future__ import annotations

import json

import pytest

from cogmembench.runners import CognitiveV2Runner
from cogmembench.scenarios.generators import generate_bitemporal_belief_revision
from cogmembench.scenarios.schema import save_jsonl
from cogmembench.substrate import (
    ABLATION_SPECS,
    AblatedSubstrateAdapter,
    AblationFeature,
    ArtifactKind,
    CognitiveArtifact,
    EpistemicStatus,
    ReferenceSubstrateAdapter,
    RelationKind,
    TimeInterval,
    UnsupportedCapabilityError,
)


def artifact(
    artifact_id: str,
    kind: ArtifactKind,
    content: str,
    valid_start: int = 5,
) -> CognitiveArtifact:
    return CognitiveArtifact(
        artifact_id=artifact_id,
        kind=kind,
        content=content,
        scenario_id="ablation-world",
        valid_time=TimeInterval(valid_start),
        epistemic_status=EpistemicStatus.ACCEPTED,
        provenance_event_ids=("event-1",),
    )


def adapter(feature: AblationFeature) -> AblatedSubstrateAdapter:
    result = AblatedSubstrateAdapter(ReferenceSubstrateAdapter(), feature)
    result.reset("ablation-world")
    return result


def test_required_ablation_registry_is_complete_and_single_feature() -> None:
    assert set(ABLATION_SPECS) == set(AblationFeature)
    assert len(ABLATION_SPECS) == 9
    assert all(spec.removed_operations for spec in ABLATION_SPECS.values())


def test_provenance_and_dependency_ablations_remove_only_targeted_state() -> None:
    provenance = adapter(AblationFeature.NO_PROVENANCE_LINKS)
    stored = provenance.commit(artifact("claim", ArtifactKind.CLAIM, "claim alpha"), 10)
    evidence = provenance.commit(artifact("evidence", ArtifactKind.EVIDENCE, "evidence alpha"), 10)
    relation = provenance.link(
        evidence.artifact_id,
        RelationKind.DERIVED_FROM,
        stored.artifact_id,
        10,
    )
    assert stored.provenance_event_ids == ()
    assert relation.metadata["persisted"] is False
    assert provenance.snapshot().relations == ()

    dependency = adapter(AblationFeature.NO_DEPENDENCY_TRACKING)
    dependency.commit(artifact("a", ArtifactKind.CLAIM, "alpha"), 10)
    dependency.commit(artifact("b", ArtifactKind.DECISION, "beta"), 10)
    dependency.link("a", RelationKind.DEPENDS_ON, "b", 10)
    assert dependency.snapshot().relations == ()


def test_artifact_kind_and_storage_ablations_remove_the_declared_feature() -> None:
    distinction = adapter(AblationFeature.NO_EVIDENCE_CLAIM_DISTINCTION)
    evidence = distinction.commit(artifact("e", ArtifactKind.EVIDENCE, "alpha evidence"), 10)
    claim = distinction.commit(artifact("c", ArtifactKind.CLAIM, "alpha claim"), 10)
    assert {evidence.kind, claim.kind} == {ArtifactKind.OBSERVATION}

    intermediate = adapter(AblationFeature.NO_STORED_INTERMEDIATE_CONCLUSIONS)
    intermediate.commit(artifact("h", ArtifactKind.HYPOTHESIS, "alpha hypothesis"), 10)
    intermediate.commit(artifact("c", ArtifactKind.CONCLUSION, "alpha conclusion"), 10)
    intermediate.commit(artifact("e", ArtifactKind.EVIDENCE, "alpha evidence"), 10)
    assert {row.artifact_id for row in intermediate.snapshot().artifacts} == {"e"}

    lessons = adapter(AblationFeature.NO_LESSON_CONSOLIDATION)
    lessons.commit(artifact("lesson", ArtifactKind.LESSON, "alpha lesson"), 10)
    assert lessons.snapshot().artifacts == ()


def test_temporal_and_supersession_ablations_destroy_historical_discrimination() -> None:
    temporal = adapter(AblationFeature.NO_TEMPORAL_METADATA)
    temporal.commit(artifact("old", ArtifactKind.CLAIM, "alpha old"), 10)
    temporal.revise("old", artifact("new", ArtifactKind.CLAIM, "alpha new"), 20)
    historical = temporal.snapshot(valid_at=5, known_at=15)
    assert {row.artifact_id for row in historical.artifacts} == {"new"}
    assert not temporal.capability_manifest().snapshot

    supersession = adapter(AblationFeature.NO_SUPERSESSION)
    supersession.commit(artifact("old", ArtifactKind.CLAIM, "alpha old"), 10)
    revised = supersession.revise(
        "old", artifact("new", ArtifactKind.CLAIM, "alpha new"), 20
    )
    assert revised.revision_of is None
    assert {row.artifact_id for row in supersession.snapshot().artifacts} == {"old", "new"}
    assert not supersession.capability_manifest().revision


def test_audit_receipt_ablation_is_explicitly_unavailable() -> None:
    no_audit = adapter(AblationFeature.NO_AUDIT_RECEIPT)
    no_audit.commit(artifact("decision", ArtifactKind.DECISION, "choose alpha"), 10)

    with pytest.raises(UnsupportedCapabilityError):
        no_audit.export_audit("decision")

    assert not no_audit.capability_manifest().audit_export


def test_runner_records_policy_ablation_and_removes_active_retrieval_tool(tmp_path) -> None:
    path = tmp_path / "scenarios.jsonl"
    save_jsonl(path, generate_bitemporal_belief_revision(42, variants=1))
    runner = CognitiveV2Runner(
        conditions=["automatic-passive", "agent-directed-active"],
        ablation=AblationFeature.NO_ACTIVE_RETRIEVAL.value,
        run_id="ablation-test",
        results_root=tmp_path / "results",
    )

    manifest = runner.run(path)
    rows = [json.loads(line) for line in runner.evaluated_path.read_text().splitlines()]
    active = next(row for row in rows if row["condition"] == "agent-directed-active")
    passive = next(row for row in rows if row["condition"] == "automatic-passive")

    assert manifest["ablation"]["feature"] == "no-active-retrieval"
    assert active["ablation_applied"]
    assert active["disabled_tools"] == ["substrate_retrieve"]
    assert active["metrics"]["tool_calls_by_type"].get("substrate_retrieve", 0) == 0
    assert passive["ablation_status"] == "no-condition-opportunity"
    assert not passive["ablation_applied"]
