from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from ..scenarios.schema import Scenario
from ..scenarios.world import CognitiveWorld, LedgerEntry, LedgerOperation
from ..substrate import (
    ArtifactKind,
    ReferenceSubstrateAdapter,
    RelationKind,
    SubstrateAdapter,
)


class CognitiveVerticalSliceExecutor:
    """Phase-driven oracle-capture executor for the first cognitive-v2 family."""

    def __init__(self, adapter: SubstrateAdapter | None = None) -> None:
        self.adapter = adapter or ReferenceSubstrateAdapter()

    def _apply(self, entry: LedgerEntry) -> None:
        if entry.operation is LedgerOperation.COMMIT:
            if entry.artifact is None:
                raise ValueError("commit ledger entry has no artifact")
            self.adapter.commit(entry.artifact, entry.logical_time)
            return
        if entry.operation is LedgerOperation.REVISE:
            if entry.artifact is None or entry.target_id is None:
                raise ValueError("revise ledger entry is incomplete")
            self.adapter.revise(entry.target_id, entry.artifact, entry.logical_time)
            return
        if entry.operation is LedgerOperation.LINK:
            if entry.source_id is None or entry.target_id is None or entry.relation is None:
                raise ValueError("link ledger entry is incomplete")
            self.adapter.link(
                entry.source_id,
                entry.relation,
                entry.target_id,
                entry.logical_time,
                strength=entry.strength,
                metadata=entry.metadata,
            )
            return
        raise ValueError(f"unsupported ledger operation: {entry.operation}")

    def run(self, scenario: Scenario) -> dict[str, Any]:
        world = CognitiveWorld.from_hidden_world(scenario.hidden_world)
        if world.ledger.scenario_id != scenario.public.scenario_id:
            raise ValueError("public scenario and hidden ledger IDs do not match")
        self.adapter.reset(scenario.public.scenario_id)
        pending: dict[int, list[LedgerEntry]] = defaultdict(list)
        for entry in world.ledger.entries:
            pending[entry.logical_time].append(entry)

        phase_trace: list[dict[str, Any]] = []
        previous_session: str | None = None
        for event in scenario.public.events:
            if event.report_time is None or event.phase is None:
                raise ValueError("cognitive-v2 execution requires timed, phased events")
            if previous_session is not None and previous_session != event.session_id:
                self.adapter.close_session(previous_session, event.report_time)
            observed = self.adapter.observe(event, event.report_time)
            operations = []
            for logical_time in sorted(time for time in pending if time <= event.report_time):
                entries = pending.pop(logical_time)
                for entry in entries:
                    self._apply(entry)
                    operations.append(entry.operation.value)
            self.adapter.quiesce()
            phase_trace.append(
                {
                    "event_id": event.event_id,
                    "phase": event.phase,
                    "logical_time": event.report_time,
                    "observation_id": observed.artifact_id,
                    "ledger_operations": operations,
                }
            )
            previous_session = event.session_id
        if pending:
            raise ValueError(
                f"ledger contains transitions after the public stream: {sorted(pending)}"
            )
        if previous_session is not None:
            final_time = scenario.public.events[-1].report_time
            if final_time is None:
                raise ValueError("final event has no report_time")
            self.adapter.close_session(previous_session, final_time)
        self.adapter.quiesce()

        temporal_results = []
        answers: dict[str, str] = {}
        for probe in world.temporal_probes:
            snapshot = self.adapter.snapshot(probe.valid_at, probe.known_at)
            candidates = [
                artifact
                for artifact in snapshot.artifacts
                if artifact.kind is ArtifactKind.CLAIM
                and artifact.structured_content.get("subject_key") == probe.subject_key
            ]
            candidates.sort(
                key=lambda artifact: (
                    artifact.transaction_time.start if artifact.transaction_time else -1,
                    artifact.artifact_id,
                ),
                reverse=True,
            )
            selected = candidates[0] if candidates else None
            value = str(selected.structured_content.get("answer_value", "")) if selected else ""
            result = {
                "probe_id": probe.probe_id,
                "checkpoint_id": probe.checkpoint_id,
                "valid_at": probe.valid_at,
                "known_at": probe.known_at,
                "candidate_artifact_ids": [row.artifact_id for row in candidates],
                "selected_artifact_id": selected.artifact_id if selected else None,
                "selected_value": value,
                "selected_valid_at": bool(
                    selected and selected.valid_time.contains(probe.valid_at)
                ),
            }
            temporal_results.append(result)
            scope = probe.subject_key.rsplit("::", 1)[-1]
            answers[probe.checkpoint_id] = json.dumps(
                {
                    "value": value,
                    "scope": scope,
                    "knowledge_state": (
                        "corrected" if selected and selected.revision_of else "provisional"
                    ),
                },
                sort_keys=True,
            )

        repair = world.repair_probe
        repair_snapshot = self.adapter.snapshot(known_at=repair.known_at)
        invalidated = sorted(
            {
                relation.target_id
                for relation in repair_snapshot.relations
                if relation.kind is RelationKind.INVALIDATES
            }
        )
        active_ids = {artifact.artifact_id for artifact in repair_snapshot.artifacts}
        preserved = sorted(set(repair.preserved_artifact_ids) & active_ids)
        repair_result = {
            "probe_id": repair.probe_id,
            "checkpoint_id": repair.checkpoint_id,
            "known_at": repair.known_at,
            "invalidated_artifact_ids": invalidated,
            "preserved_artifact_ids": preserved,
        }
        answers[repair.checkpoint_id] = json.dumps(
            {"invalidated": invalidated, "preserved": preserved},
            sort_keys=True,
        )
        current_snapshot = self.adapter.snapshot()
        return {
            "scenario_id": scenario.public.scenario_id,
            "family": scenario.public.family,
            "condition": "oracle-reference-v2",
            "answer": answers[scenario.public.events[-1].checkpoint_id or "repair"],
            "answers": answers,
            "temporal_probe_results": temporal_results,
            "repair_probe_result": repair_result,
            "phase_trace": phase_trace,
            "snapshot": {
                "snapshot_id": current_snapshot.snapshot_id,
                "artifact_ids": [row.artifact_id for row in current_snapshot.artifacts],
                "relation_ids": [row.relation_id for row in current_snapshot.relations],
            },
            "usage": self.adapter.usage_report(),
            "capabilities": self.adapter.capability_manifest(),
        }
