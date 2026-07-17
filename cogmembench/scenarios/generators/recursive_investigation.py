from __future__ import annotations

from ...difficulty import DifficultyTier, difficulty_for_variant
from ...environments import IncidentWorld, generate_incident_world
from ...telemetry.tokens import count_tokens
from ..derivation import (
    DerivationDAG,
    DerivationNode,
    DerivationNodeKind,
    ReDerivabilityControl,
)
from ..schema import Event, EvaluatorSpec, ExpectedMemory, PublicScenario, Scenario
from ..world import ScenarioPhase


def _premise_text(world: IncidentWorld, index: int) -> str:
    normal_metrics = " ".join(f"metric_{index}_{item}=normal" for item in range(18))
    if index == 0:
        clue = f"Inspection of {world.root_service}: {world.root_signal}."
    elif index == 1:
        clue = f"The {world.alert_service} errors reproduce along a path to {world.root_service}."
    elif index == 2:
        clue = f"A control probe outside {world.root_service} remains healthy."
    elif index == 3:
        clue = f"The failure signature is consistent with {world.root_cause}."
    elif index == 4:
        clue = f"The remediation catalog maps this signature to {world.correct_remediation}."
    else:
        clue = "The symptom disappears when the implicated dependency is isolated."
    return f"Diagnostic shard {index + 1}: {clue} Distractor telemetry: {normal_metrics}."


def _corrected_incident_world(
    initial: IncidentWorld, seed: int, variant: int
) -> IncidentWorld:
    """Mint a different causal mechanism over the same observable service graph."""
    candidate = generate_incident_world(seed + 500_000, variant)
    for offset in range(1, 6):
        candidate_role = candidate.root_service.split("-", 1)[0]
        initial_role = initial.root_service.split("-", 1)[0]
        if candidate_role != initial_role:
            break
        candidate = generate_incident_world(seed + 500_000 + offset, variant)
    root_service = next(
        service for service in initial.services if service.startswith(f"{candidate_role}-")
    )
    distractors = tuple(
        f"restart unaffected service {service}"
        for service in initial.services
        if service != root_service
    )[:4]
    return IncidentWorld(
        world_id=f"{initial.world_id}-corrected",
        services=initial.services,
        dependencies=initial.dependencies,
        alert_service=initial.alert_service,
        root_service=root_service,
        root_cause=candidate.root_cause,
        root_signal=candidate.root_signal,
        correct_remediation=candidate.correct_remediation,
        distractor_remediations=distractors,
        difficulty_tier=initial.difficulty_tier,
        realization_pattern=initial.realization_pattern,
    )


def _derived_nodes(
    sid: str,
    premise_nodes: tuple[DerivationNode, ...],
    tier: DifficultyTier,
) -> tuple[DerivationNode, ...]:
    def intermediate(name: str, inputs: tuple[str, ...], tokens: int) -> DerivationNode:
        return DerivationNode(
            f"{sid}:{name}",
            DerivationNodeKind.INTERMEDIATE,
            inputs,
            "derive",
            tokens,
        )

    if tier is DifficultyTier.EASY:
        a = intermediate(
            "hypothesis-a", tuple(node.artifact_id for node in premise_nodes[:3]), 18
        )
        b = intermediate(
            "hypothesis-b", tuple(node.artifact_id for node in premise_nodes[3:5]), 16
        )
        intermediates = (a, b)
        conclusion_inputs = (a.artifact_id, b.artifact_id, premise_nodes[5].artifact_id)
    elif tier is DifficultyTier.MEDIUM:
        a = intermediate(
            "hypothesis-a", tuple(node.artifact_id for node in premise_nodes[:2]), 18
        )
        b = intermediate(
            "hypothesis-b",
            (a.artifact_id, premise_nodes[2].artifact_id, premise_nodes[3].artifact_id),
            16,
        )
        intermediates = (a, b)
        conclusion_inputs = (
            b.artifact_id,
            premise_nodes[4].artifact_id,
            premise_nodes[5].artifact_id,
            premise_nodes[6].artifact_id,
        )
    else:
        a = intermediate(
            "hypothesis-a", tuple(node.artifact_id for node in premise_nodes[:2]), 18
        )
        b = intermediate(
            "hypothesis-b", (a.artifact_id, premise_nodes[2].artifact_id), 17
        )
        c = intermediate(
            "hypothesis-c",
            (b.artifact_id, premise_nodes[3].artifact_id, premise_nodes[4].artifact_id),
            16,
        )
        intermediates = (a, b, c)
        conclusion_inputs = (
            c.artifact_id,
            premise_nodes[5].artifact_id,
            premise_nodes[6].artifact_id,
            premise_nodes[7].artifact_id,
        )
    conclusion = DerivationNode(
        f"{sid}:conclusion",
        DerivationNodeKind.CONCLUSION,
        conclusion_inputs,
        "derive",
        20,
        required_for_reuse=True,
    )
    decision = DerivationNode(
        f"{sid}:reuse-decision",
        DerivationNodeKind.DECISION,
        (conclusion.artifact_id,),
        "reuse",
        12,
    )
    return (*intermediates, conclusion, decision)


def generate_recursive_investigation(
    seed: int,
    max_agent_steps: int = 8,
    variants: int = 5,
) -> list[Scenario]:
    if variants <= 0:
        raise ValueError("variants must be positive")
    scenarios = []
    for variant in range(variants):
        incident = generate_incident_world(seed, variant)
        corrected_incident = _corrected_incident_world(incident, seed, variant)
        tier = difficulty_for_variant(variant)
        sid = f"recursive-{seed}-{variant:02d}"
        premise_count = {
            DifficultyTier.EASY: 6,
            DifficultyTier.MEDIUM: 7,
            DifficultyTier.HARD: 8,
        }[tier]
        premise_texts = tuple(_premise_text(incident, index) for index in range(premise_count))
        events = [
            Event(
                "alert",
                1,
                "user",
                f"Incident {incident.world_id}: elevated errors at {incident.alert_service}. "
                f"Services and dependencies: {incident.public_brief()['dependencies']}.",
                event_time=10,
                report_time=10,
                event_id=f"{sid}:event:alert",
                phase=ScenarioPhase.ACCUMULATE.value,
            )
        ]
        for index, text in enumerate(premise_texts):
            logical_time = 11 + index
            events.append(
                Event(
                    f"evidence-{index + 1}",
                    1,
                    "user",
                    text,
                    event_time=logical_time,
                    report_time=logical_time,
                    event_id=f"{sid}:event:premise-{index + 1}",
                    phase=ScenarioPhase.ACCUMULATE.value,
                )
            )
        events.extend(
            (
                Event(
                    "derive",
                    1,
                    "user",
                    "Derive and store the incident conclusion. Return JSON with root_service, "
                    "root_cause, remediation, and confidence from 0 to 1.",
                    evaluate=True,
                    checkpoint_id="derive",
                    event_time=20,
                    report_time=20,
                    event_id=f"{sid}:event:derive",
                    phase=ScenarioPhase.DERIVE.value,
                ),
                Event(
                    "reuse",
                    1,
                    "user",
                    "A later incident matches the previously derived failure signature. The raw "
                    "diagnostic shards exceed this turn's read budget. Reuse the stored conclusion "
                    "and return JSON with root_service, root_cause, remediation, basis, and "
                    "confidence from 0 to 1.",
                    evaluate=True,
                    checkpoint_id="reuse",
                    event_time=40,
                    report_time=40,
                    event_id=f"{sid}:event:reuse",
                    phase=ScenarioPhase.REUSE.value,
                ),
                Event(
                    "invalidate",
                    1,
                    "user",
                    f"Forensic correction: diagnostic shard 1 came from a cross-wired sensor "
                    f"and is rejected. Replacement inspection of "
                    f"{corrected_incident.root_service}: {corrected_incident.root_signal}. "
                    f"The corrected failure signature is {corrected_incident.root_cause}; the "
                    f"remediation catalog now maps it to "
                    f"{corrected_incident.correct_remediation}. The stored conclusion derived "
                    "from the rejected shard must be revised.",
                    event_time=15,
                    report_time=50,
                    event_id=f"{sid}:event:invalidate",
                    phase=ScenarioPhase.PERTURB.value,
                ),
                Event(
                    "repair",
                    1,
                    "user",
                    "Repair and store the incident conclusion after the forensic correction. "
                    "Do not retain the rejected conclusion as current. Return JSON with "
                    "root_service, root_cause, remediation, superseded_conclusion, and "
                    "confidence from 0 to 1.",
                    evaluate=True,
                    checkpoint_id="repair",
                    event_time=60,
                    report_time=60,
                    event_id=f"{sid}:event:repair",
                    phase=ScenarioPhase.REPAIR.value,
                ),
                Event(
                    "reuse-repaired",
                    1,
                    "user",
                    "A later incident matches the corrected failure signature. The raw diagnostic "
                    "shards again exceed the read budget. Reuse the revised conclusion and return "
                    "JSON with root_service, root_cause, remediation, basis, and confidence from "
                    "0 to 1.",
                    evaluate=True,
                    checkpoint_id="reuse_repaired",
                    event_time=70,
                    report_time=70,
                    event_id=f"{sid}:event:reuse-repaired",
                    phase=ScenarioPhase.REUSE.value,
                ),
            )
        )
        premise_nodes = tuple(
            DerivationNode(
                f"{sid}:premise-{index + 1}",
                DerivationNodeKind.PREMISE,
                (),
                f"evidence-{index + 1}",
                count_tokens(text),
            )
            for index, text in enumerate(premise_texts)
        )
        derived_nodes = _derived_nodes(sid, premise_nodes, tier)
        conclusion = next(
            node for node in derived_nodes if node.kind is DerivationNodeKind.CONCLUSION
        )
        decision = next(node for node in derived_nodes if node.kind is DerivationNodeKind.DECISION)
        dag = DerivationDAG((*premise_nodes, *derived_nodes))
        control = ReDerivabilityControl(
            read_budget_tokens=100,
            raw_premise_tokens=sum(node.token_count for node in premise_nodes),
            derived_artifact_tokens=conclusion.token_count,
            premise_session_count=len({node.session_id for node in premise_nodes}),
        )
        expected = {
            "root_service": incident.root_service,
            "root_cause": incident.root_cause,
            "remediation": incident.correct_remediation,
        }
        corrected_expected = {
            "root_service": corrected_incident.root_service,
            "root_cause": corrected_incident.root_cause,
            "remediation": corrected_incident.correct_remediation,
        }
        revised_conclusion_id = f"{sid}:conclusion-revised"
        scenarios.append(
            Scenario(
                PublicScenario(
                    sid,
                    "recursive_investigation",
                    seed,
                    variant,
                    tuple(events),
                    max_agent_steps,
                    schema_version=2,
                ),
                EvaluatorSpec(
                    {**corrected_expected, "basis": "revised conclusion"},
                    (
                        ExpectedMemory(
                            conclusion.artifact_id,
                            "conclusion",
                            f"{incident.root_cause} at {incident.root_service}; "
                            f"use {incident.correct_remediation}",
                            source_session="derive",
                            provenance=tuple(node.artifact_id for node in premise_nodes),
                        ),
                        ExpectedMemory(
                            revised_conclusion_id,
                            "conclusion",
                            f"{corrected_incident.root_cause} at "
                            f"{corrected_incident.root_service}; use "
                            f"{corrected_incident.correct_remediation}",
                            source_session="repair",
                            supersedes=conclusion.artifact_id,
                            provenance=(premise_nodes[0].artifact_id,),
                        ),
                    ),
                    expected_answers={
                        "derive": expected,
                        "reuse": {**expected, "basis": "stored conclusion"},
                        "repair": {
                            **corrected_expected,
                            "superseded_conclusion": incident.root_cause,
                        },
                        "reuse_repaired": {
                            **corrected_expected,
                            "basis": "revised conclusion",
                        },
                    },
                    expected_retrieval_ids=(conclusion.artifact_id, revised_conclusion_id),
                    category="recursive_investigation",
                ),
                {
                    "recursive_world_schema": 3,
                    "incident_world": incident.to_dict(),
                    "corrected_incident_world": corrected_incident.to_dict(),
                    "derivation_dag": dag.to_dict(),
                    "rederivability_control": control.to_dict(),
                    "required_reuse_artifact_id": conclusion.artifact_id,
                    "required_repaired_reuse_artifact_id": revised_conclusion_id,
                    "derivation_depth": dag.depth(decision.artifact_id),
                    "derivation_breadth": dag.breadth(),
                    "difficulty_tier": tier.value,
                    "realization_pattern": f"derivation-depth-{dag.depth(decision.artifact_id)}",
                    "failure_amplification_control": {
                        "invalidated_premise_id": premise_nodes[0].artifact_id,
                        "stale_conclusion_id": conclusion.artifact_id,
                        "revised_conclusion_id": revised_conclusion_id,
                        "revision_depth": dag.depth(decision.artifact_id),
                    },
                },
            )
        )
    return scenarios
