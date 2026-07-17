from __future__ import annotations

import json
from typing import Any

from ..environments import (
    ActionKind,
    IncidentAction,
    IncidentWorld,
    ServiceIncidentEnvironment,
    execution_score,
)
from ..scenarios.derivation import DerivationDAG, DerivationNodeKind, ReDerivabilityControl
from ..scenarios.schema import Scenario
from ..substrate import (
    ArtifactKind,
    CognitiveArtifact,
    EpistemicStatus,
    ReferenceSubstrateAdapter,
    RetrievalBudget,
    SubstrateAdapter,
    TimeInterval,
)


class RecursiveInvestigationOracleExecutor:
    """Mechanical oracle ceiling for recursive reuse plus incident execution."""

    def __init__(self, adapter: SubstrateAdapter | None = None) -> None:
        self.adapter = adapter or ReferenceSubstrateAdapter()

    def run(self, scenario: Scenario) -> dict[str, Any]:
        hidden = scenario.hidden_world
        if hidden.get("recursive_world_schema") != 3:
            raise ValueError("scenario is not a recursive investigation world")
        incident = IncidentWorld.from_dict(hidden["incident_world"])
        corrected_incident = IncidentWorld.from_dict(hidden["corrected_incident_world"])
        dag = DerivationDAG.from_dict(hidden["derivation_dag"])
        control = ReDerivabilityControl.from_dict(hidden["rederivability_control"])
        conclusion_id = str(hidden["required_reuse_artifact_id"])
        revised_conclusion_id = str(hidden["required_repaired_reuse_artifact_id"])
        amplification = hidden["failure_amplification_control"]
        adapter = self.adapter
        adapter.reset(scenario.public.scenario_id)

        premise_nodes = [node for node in dag.nodes if node.kind is DerivationNodeKind.PREMISE]
        conclusion_node = next(node for node in dag.nodes if node.artifact_id == conclusion_id)
        for index, node in enumerate(premise_nodes):
            event = scenario.public.events[index + 1]
            adapter.commit(
                CognitiveArtifact(
                    artifact_id=node.artifact_id,
                    kind=ArtifactKind.EVIDENCE,
                    content=event.content,
                    scenario_id=scenario.public.scenario_id,
                    valid_time=TimeInterval(event.event_time or 0),
                    epistemic_status=EpistemicStatus.ACCEPTED,
                    session_id=node.session_id,
                    provenance_event_ids=(str(event.event_id),),
                ),
                event.report_time or 0,
            )
        conclusion_text = (
            f"Stored failure signature conclusion: {incident.root_cause} at "
            f"{incident.root_service}; remediate by {incident.correct_remediation}."
        )
        adapter.commit(
            CognitiveArtifact(
                artifact_id=conclusion_id,
                kind=ArtifactKind.CONCLUSION,
                content=conclusion_text,
                scenario_id=scenario.public.scenario_id,
                valid_time=TimeInterval(20),
                structured_content={"token_count": conclusion_node.token_count},
                epistemic_status=EpistemicStatus.ACCEPTED,
                session_id="derive",
                provenance_event_ids=tuple(
                    str(scenario.public.events[index + 1].event_id)
                    for index, _ in enumerate(premise_nodes)
                ),
            ),
            20,
        )
        retrieval = adapter.retrieve(
            f"stored failure signature {incident.root_service}",
            RetrievalBudget(1, max_context_tokens=control.read_budget_tokens),
            40,
        )
        context_ids = [item.artifact.artifact_id for item in retrieval.items]

        correction_event = next(
            event for event in scenario.public.events if event.session_id == "invalidate"
        )
        invalidated_premise_id = str(amplification["invalidated_premise_id"])
        adapter.revise(
            invalidated_premise_id,
            CognitiveArtifact(
                artifact_id=f"{scenario.public.scenario_id}:premise-replacement",
                kind=ArtifactKind.EVIDENCE,
                content=correction_event.content,
                scenario_id=scenario.public.scenario_id,
                valid_time=TimeInterval(correction_event.event_time or 0),
                epistemic_status=EpistemicStatus.ACCEPTED,
                session_id="invalidate",
                provenance_event_ids=(str(correction_event.event_id),),
            ),
            correction_event.report_time or 50,
        )
        revised_conclusion_text = (
            f"Revised failure signature conclusion: {corrected_incident.root_cause} at "
            f"{corrected_incident.root_service}; remediate by "
            f"{corrected_incident.correct_remediation}."
        )
        adapter.revise(
            conclusion_id,
            CognitiveArtifact(
                artifact_id=revised_conclusion_id,
                kind=ArtifactKind.CONCLUSION,
                content=revised_conclusion_text,
                scenario_id=scenario.public.scenario_id,
                valid_time=TimeInterval(15),
                structured_content={"token_count": conclusion_node.token_count},
                epistemic_status=EpistemicStatus.ACCEPTED,
                session_id="repair",
                provenance_event_ids=(str(correction_event.event_id),),
            ),
            60,
        )
        repaired_retrieval = adapter.retrieve(
            f"revised failure signature {corrected_incident.root_service}",
            RetrievalBudget(1, max_context_tokens=control.read_budget_tokens),
            70,
        )
        repaired_context_ids = [
            item.artifact.artifact_id for item in repaired_retrieval.items
        ]

        environment = ServiceIncidentEnvironment(corrected_incident)
        observations = [
            environment.step(
                IncidentAction(ActionKind.INSPECT, corrected_incident.root_service)
            ),
            environment.step(
                IncidentAction(
                    ActionKind.REMEDIATE,
                    corrected_incident.root_service,
                    corrected_incident.correct_remediation,
                )
            ),
        ]
        base_answer = {
            "root_service": incident.root_service,
            "root_cause": incident.root_cause,
            "remediation": incident.correct_remediation,
        }
        corrected_answer = {
            "root_service": corrected_incident.root_service,
            "root_cause": corrected_incident.root_cause,
            "remediation": corrected_incident.correct_remediation,
        }
        answers = {
            "derive": json.dumps(base_answer, sort_keys=True),
            "reuse": json.dumps({**base_answer, "basis": "stored conclusion"}, sort_keys=True),
            "repair": json.dumps(
                {**corrected_answer, "superseded_conclusion": incident.root_cause},
                sort_keys=True,
            ),
            "reuse_repaired": json.dumps(
                {**corrected_answer, "basis": "revised conclusion"},
                sort_keys=True,
            ),
        }
        return {
            "scenario_id": scenario.public.scenario_id,
            "family": scenario.public.family,
            "condition": "oracle-reference-v2",
            "answer": answers["reuse_repaired"],
            "answers": answers,
            "decision_context_artifact_ids": context_ids,
            "decision_context_tokens": sum(
                int(item.artifact.structured_content.get("token_count", 20))
                for item in retrieval.items
            ),
            "repaired_decision_context_artifact_ids": repaired_context_ids,
            "repaired_decision_context_tokens": sum(
                int(item.artifact.structured_content.get("token_count", 20))
                for item in repaired_retrieval.items
            ),
            "environment_observations": [
                {
                    "step": row.step,
                    "message": row.message,
                    "signals": list(row.signals),
                    "cost": row.cost,
                    "resolved": row.resolved,
                }
                for row in observations
            ],
            "execution": execution_score(environment),
            "derivation_depth": dag.depth(f"{scenario.public.scenario_id}:reuse-decision"),
            "derivation_breadth": dag.breadth(),
        }
