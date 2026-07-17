from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ..environments import (
    ActionKind,
    IncidentAction,
    IncidentWorld,
    ServiceIncidentEnvironment,
    execution_score,
)
from ..scenarios.schema import Scenario
from ..scenarios.world import LedgerOperation, WorldLedger
from ..substrate import ReferenceSubstrateAdapter, RetrievalBudget, SubstrateAdapter


class DecisionLineageOracleExecutor:
    """Replay a decision ledger while preserving the harness decision-time trace."""

    def __init__(self, adapter: SubstrateAdapter | None = None) -> None:
        self.adapter = adapter or ReferenceSubstrateAdapter()

    def run(self, scenario: Scenario) -> dict[str, Any]:
        hidden = scenario.hidden_world
        if hidden.get("decision_world_schema") != 2:
            raise ValueError("scenario is not a decision-lineage world")
        ledger = WorldLedger.from_dict(hidden["world_ledger"])
        adapter = self.adapter
        adapter.reset(scenario.public.scenario_id)
        decision_context_ids = set(hidden["decision_context_ids"])
        trace_ids: list[str] = []
        trace_time = 11
        for entry in ledger.entries:
            if entry.operation is LedgerOperation.COMMIT:
                if entry.artifact is None:
                    raise ValueError("commit entry is incomplete")
                if entry.artifact.artifact_id == hidden["decision_ref"]:
                    retrieval = adapter.retrieve(
                        "decision evidence constraint",
                        RetrievalBudget(10),
                        trace_time,
                    )
                    trace_ids = [
                        item.artifact.artifact_id
                        for item in retrieval.items
                        if item.artifact.artifact_id in decision_context_ids
                    ]
                adapter.commit(entry.artifact, entry.logical_time)
            elif entry.operation is LedgerOperation.LINK:
                if not entry.source_id or not entry.target_id or entry.relation is None:
                    raise ValueError("link entry is incomplete")
                adapter.link(
                    entry.source_id,
                    entry.relation,
                    entry.target_id,
                    entry.logical_time,
                )
            else:
                raise ValueError("decision lineage oracle does not expect revisions")
        receipt = adapter.export_audit(str(hidden["decision_ref"]))
        incident = IncidentWorld.from_dict(hidden["incident_world"])
        environment = ServiceIncidentEnvironment(incident)
        environment.step(
            IncidentAction(
                ActionKind.REMEDIATE,
                incident.root_service,
                incident.correct_remediation,
            )
        )
        return {
            "scenario_id": scenario.public.scenario_id,
            "family": scenario.public.family,
            "condition": "oracle-reference-v2",
            "decision_trace": {
                "decision_time": int(hidden["decision_time"]),
                "retrieval_time": trace_time,
                "retrieved_artifact_ids": trace_ids,
            },
            "audit_receipt": asdict(receipt),
            "execution": execution_score(environment),
        }
