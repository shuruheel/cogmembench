from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace

import pytest

from cogmembench.scenarios.schema import Event, PublicScenario, Scenario
from cogmembench.substrate import (
    ArtifactKind,
    ClockMode,
    CognitiveArtifact,
    EpistemicStatus,
    FlatSubstrateAdapter,
    ReferenceSubstrateAdapter,
    RelationKind,
    RetrievalBudget,
    SubstrateAdapter,
    TimeInterval,
    UsageFidelity,
    render_canonical_artifact,
)
from cogmembench.substrate.adapter import ClockOrderError, IsolationError
from cogmembench.validation import validate_adapter_contract


def artifact(
    artifact_id: str,
    kind: ArtifactKind,
    content: str,
    *,
    valid_start: int = 0,
    **changes,
) -> CognitiveArtifact:
    return CognitiveArtifact(
        artifact_id=artifact_id,
        kind=kind,
        content=content,
        scenario_id="world-1",
        valid_time=TimeInterval(valid_start),
        epistemic_status=EpistemicStatus.ACCEPTED,
        **changes,
    )


def test_schema_v1_round_trip_keeps_optional_times_absent():
    data = {
        "public": {
            "scenario_id": "legacy",
            "family": "compatibility",
            "seed": 1,
            "variant": 0,
            "events": [
                {
                    "session_id": "s1",
                    "turn_id": 1,
                    "role": "user",
                    "content": "legacy event",
                }
            ],
        },
        "evaluator": {"expected_answer": {}, "durable": []},
    }

    scenario = Scenario.from_dict(data)

    assert scenario.public.schema_version == 1
    assert scenario.public.events[0].event_time is None
    assert scenario.public.events[0].report_time is None
    normalized = scenario.public.to_dict()
    assert "schema_version" not in normalized
    assert "event_time" not in normalized["events"][0]
    assert "report_time" not in normalized["events"][0]

    legacy_shape = asdict(scenario.public)
    legacy_shape.pop("schema_version")
    for event in legacy_shape["events"]:
        event.pop("event_time")
        event.pop("report_time")
        event.pop("event_id")
        event.pop("phase")
    legacy_raw = json.dumps(legacy_shape, sort_keys=True, separators=(",", ":"))
    assert scenario.public_hash() == hashlib.sha256(legacy_raw.encode()).hexdigest()


def test_schema_v2_requires_complete_strictly_ordered_logical_times():
    events = (
        Event(
            "s1",
            1,
            "user",
            "reported later",
            event_time=4,
            report_time=10,
            event_id="e1",
            phase="accumulate",
        ),
        Event(
            "s2",
            1,
            "user",
            "future effective",
            event_time=20,
            report_time=11,
            event_id="e2",
            phase="perturb",
        ),
    )

    scenario = PublicScenario("v2", "temporal", 1, 0, events, schema_version=2)

    assert scenario.events[0].event_time == 4
    with pytest.raises(ValueError, match="strictly increasing"):
        PublicScenario(
            "invalid",
            "temporal",
            1,
            0,
            (events[0], replace(events[1], report_time=10)),
            schema_version=2,
        )
    with pytest.raises(ValueError, match="require event_time"):
        PublicScenario(
            "missing",
            "temporal",
            1,
            0,
            (replace(events[0], event_time=None),),
            schema_version=2,
        )


def test_reference_adapter_is_a_v2_adapter_and_requires_a_namespace():
    adapter = ReferenceSubstrateAdapter()

    assert isinstance(adapter, SubstrateAdapter)
    with pytest.raises(IsolationError):
        adapter.snapshot()

    adapter.reset("world-1")
    manifest = adapter.capability_manifest()
    assert manifest.clock_mode is ClockMode.NATIVE
    assert manifest.snapshot
    assert not manifest.branching


def test_reference_adapter_supports_bitemporal_revision_views():
    adapter = ReferenceSubstrateAdapter()
    adapter.reset("world-1")
    original = adapter.commit(
        artifact("claim-old", ArtifactKind.CLAIM, "Launch is March 12", valid_start=10),
        logical_time=20,
    )
    revision = artifact(
        "claim-new",
        ArtifactKind.CLAIM,
        "Launch is March 21",
        valid_start=10,
    )

    first_revision = adapter.revise(original.artifact_id, revision, logical_time=30)
    repeated_revision = adapter.revise(original.artifact_id, revision, logical_time=30)

    before = adapter.snapshot(valid_at=15, known_at=29)
    after = adapter.snapshot(valid_at=15, known_at=30)
    assert repeated_revision == first_revision
    assert [row.artifact_id for row in before.artifacts] == ["claim-old"]
    assert [row.artifact_id for row in after.artifacts] == ["claim-new"]
    assert before.valid_at == after.valid_at == 15
    assert before.known_at == 29
    assert after.known_at == 30


def test_reference_adapter_retrieval_honors_item_and_character_budgets():
    adapter = ReferenceSubstrateAdapter()
    adapter.reset("world-1")
    adapter.commit(artifact("a", ArtifactKind.CLAIM, "alpha launch corrected"), 1)
    adapter.commit(artifact("b", ArtifactKind.EVIDENCE, "alpha launch bulletin"), 2)

    result = adapter.retrieve(
        "alpha launch",
        RetrievalBudget(max_items=2, max_context_chars=21),
        logical_time=3,
    )

    assert len(result.items) == 1
    assert result.truncated
    assert result.items[0].artifact.artifact_id == "b"

    token_limited = adapter.retrieve(
        "alpha launch",
        RetrievalBudget(max_items=2, max_context_tokens=3),
        logical_time=4,
    )
    assert len(token_limited.items) == 1
    assert token_limited.truncated


def test_reference_adapter_audit_is_grounded_in_explicit_decision_context():
    adapter = ReferenceSubstrateAdapter()
    adapter.reset("world-1")
    adapter.commit(artifact("evidence", ArtifactKind.EVIDENCE, "authoritative bulletin"), 1)
    adapter.retrieve("authoritative bulletin", RetrievalBudget(1), logical_time=2)
    decision = adapter.commit(
        artifact(
            "decision",
            ArtifactKind.DECISION,
            "Use the corrected launch date",
            structured_content={
                "retrieved_artifact_ids": ["evidence"],
                "assumptions": ["bulletin applies to the US"],
                "alternatives": ["retain provisional date"],
            },
            provenance_event_ids=("event:s1:1",),
        ),
        3,
    )
    adapter.link("evidence", RelationKind.SUPPORTS, decision.artifact_id, 3)
    late_evidence = adapter.commit(
        artifact("late", ArtifactKind.EVIDENCE, "post-decision confirmation"), 4
    )
    adapter.link(late_evidence.artifact_id, RelationKind.SUPPORTS, decision.artifact_id, 4)

    receipt = adapter.export_audit(decision.artifact_id)

    assert receipt.evidence_ids == ("evidence",)
    assert receipt.retrieved_artifact_ids == ("evidence",)
    assert receipt.retrieval_times == (2,)
    assert receipt.source_event_ids == ("event:s1:1",)


def test_observe_requires_the_event_and_adapter_clocks_to_agree():
    adapter = ReferenceSubstrateAdapter()
    adapter.reset("world-1")
    event = Event("s1", 1, "user", "reported", event_time=1, report_time=4)

    with pytest.raises(ClockOrderError, match="report_time"):
        adapter.observe(event, logical_time=3)


def test_reference_adapter_enforces_idempotency_isolation_and_clock_order():
    adapter = ReferenceSubstrateAdapter()
    adapter.reset("world-1")
    row = artifact("claim", ArtifactKind.CLAIM, "stable content")

    first = adapter.commit(row, 4)
    second = adapter.commit(row, 4)

    assert first == second
    assert adapter.usage_report().write_operations == 1
    with pytest.raises(ClockOrderError):
        adapter.retrieve("stable", RetrievalBudget(1), logical_time=3)
    with pytest.raises(IsolationError):
        adapter.commit(replace(row, artifact_id="wrong", scenario_id="other"), 4)


def test_reference_adapter_reports_complete_zero_model_usage_without_silent_nulls():
    adapter = ReferenceSubstrateAdapter()
    adapter.reset("world-1")

    report = adapter.usage_report()

    assert report.fidelity is UsageFidelity.COMPLETE
    assert report.model_calls == 0
    assert report.input_tokens == 0
    assert report.embedding_calls == 0


def test_reference_adapter_passes_the_reusable_v2_behavioral_contract():
    result = validate_adapter_contract(ReferenceSubstrateAdapter())

    assert result["passed"]
    assert all(result["checks"].values())
    assert result["clock_mode"] == "native"


def test_flat_bm25_adapter_passes_contract_with_audit_declared_absent():
    adapter = FlatSubstrateAdapter()

    result = validate_adapter_contract(adapter)

    assert result["passed"]
    assert result["adapter"] == "flat-bm25"
    assert not adapter.capability_manifest().audit_export


def test_canonical_oracle_rendering_is_stable_and_includes_temporal_metadata():
    row = artifact("claim", ArtifactKind.CLAIM, "stable content", valid_start=4)

    first = render_canonical_artifact(row)
    second = render_canonical_artifact(row)

    assert first == second
    assert "artifact_id: claim" in first
    assert "valid_time: 4:open" in first
    assert "transaction_time: unstamped" in first
