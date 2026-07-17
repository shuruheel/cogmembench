from __future__ import annotations

from ...difficulty import DifficultyTier, difficulty_for_variant
from ...environments import generate_incident_world
from ...substrate import (
    ArtifactKind,
    CognitiveArtifact,
    EpistemicStatus,
    RelationKind,
    TimeInterval,
)
from ..schema import Event, EvaluatorSpec, ExpectedMemory, PublicScenario, Scenario
from ..world import LedgerEntry, LedgerOperation, ScenarioPhase, WorldLedger


def _artifact(
    scenario_id: str,
    artifact_id: str,
    kind: ArtifactKind,
    content: str,
    logical_time: int,
    event_id: str,
    **structured,
) -> CognitiveArtifact:
    return CognitiveArtifact(
        artifact_id=artifact_id,
        kind=kind,
        content=content,
        scenario_id=scenario_id,
        valid_time=TimeInterval(logical_time),
        structured_content=structured,
        epistemic_status=EpistemicStatus.ACCEPTED,
        actor_id="oracle-generator",
        provenance_event_ids=(event_id,),
    )


def generate_decision_lineage(
    seed: int,
    max_agent_steps: int = 8,
    variants: int = 5,
) -> list[Scenario]:
    if variants <= 0:
        raise ValueError("variants must be positive")
    scenarios = []
    for variant in range(variants):
        incident = generate_incident_world(seed + 100, variant)
        tier = difficulty_for_variant(variant)
        sid = f"decision-lineage-{seed}-{variant:02d}"
        ids = {
            name: f"{sid}:{name}"
            for name in (
                "evidence",
                "constraint",
                "assumption",
                "risk",
                "decision",
                "action",
                "outcome",
                "late",
            )
        }
        event_ids = {name: f"{sid}:event:{name}" for name in ids}
        events = (
            Event(
                "evidence",
                1,
                "user",
                f"Decision evidence for {incident.world_id}: inspection of "
                f"{incident.root_service} reports {incident.root_signal}.",
                event_time=10,
                report_time=10,
                event_id=event_ids["evidence"],
                phase=ScenarioPhase.ACCUMULATE.value,
            ),
            Event(
                "deliberate",
                1,
                "user",
                f"Decision constraint: minimize user impact. Alternatives are "
                f"{', '.join(incident.distractor_remediations)} or "
                f"{incident.correct_remediation}.",
                event_time=11,
                report_time=11,
                event_id=event_ids["constraint"],
                phase=ScenarioPhase.DECIDE.value,
            ),
            Event(
                "decide",
                1,
                "assistant",
                f"Decision: apply {incident.correct_remediation} to "
                f"{incident.root_service} based on the inspected signal and impact constraint.",
                event_time=12,
                report_time=12,
                event_id=event_ids["decision"],
                phase=ScenarioPhase.DECIDE.value,
            ),
            Event(
                "execute",
                1,
                "assistant",
                f"Executed {incident.correct_remediation} on {incident.root_service}.",
                event_time=13,
                report_time=13,
                event_id=event_ids["action"],
                phase=ScenarioPhase.EXPERIENCE.value,
            ),
            Event(
                "outcome",
                1,
                "user",
                "Outcome: service health recovered and the incident resolved.",
                event_time=14,
                report_time=14,
                event_id=event_ids["outcome"],
                phase=ScenarioPhase.EXPERIENCE.value,
            ),
            Event(
                "late",
                1,
                "user",
                f"Post-decision forensic confirmation at time 20: the hidden root cause was "
                f"{incident.root_cause}. This was not available when the decision was made.",
                event_time=10,
                report_time=20,
                event_id=event_ids["late"],
                phase=ScenarioPhase.PERTURB.value,
            ),
            Event(
                "audit",
                1,
                "user",
                "Audit the decision using only its contemporaneous evidence, assumptions, "
                "alternatives, action, and outcome. Do not leak later forensic evidence. Return "
                "JSON with evidence, constraint, decision, action, outcome, "
                "later_evidence_excluded, and confidence from 0 to 1.",
                evaluate=True,
                checkpoint_id="audit",
                event_time=30,
                report_time=30,
                event_id=f"{sid}:event:audit",
                phase=ScenarioPhase.AUDIT.value,
            ),
        )
        context_names = ["evidence", "constraint"]
        if tier in {DifficultyTier.MEDIUM, DifficultyTier.HARD}:
            context_names.append("assumption")
        if tier is DifficultyTier.HARD:
            context_names.append("risk")
        artifacts = {
            "evidence": _artifact(
                sid,
                ids["evidence"],
                ArtifactKind.EVIDENCE,
                f"Decision evidence: {incident.root_signal}",
                10,
                event_ids["evidence"],
            ),
            "constraint": _artifact(
                sid,
                ids["constraint"],
                ArtifactKind.CONSTRAINT,
                "Decision evidence constraint: minimize user impact",
                11,
                event_ids["constraint"],
            ),
            "decision": _artifact(
                sid,
                ids["decision"],
                ArtifactKind.DECISION,
                f"Apply {incident.correct_remediation} to {incident.root_service}",
                12,
                event_ids["decision"],
                retrieved_artifact_ids=[ids[name] for name in context_names],
                assumptions=["the inspected signal identifies the active failure"],
                alternatives=list(incident.distractor_remediations),
            ),
            "action": _artifact(
                sid,
                ids["action"],
                ArtifactKind.ACTION,
                f"Applied {incident.correct_remediation} to {incident.root_service}",
                13,
                event_ids["action"],
            ),
            "outcome": _artifact(
                sid,
                ids["outcome"],
                ArtifactKind.OUTCOME,
                "Incident resolved and service health recovered",
                14,
                event_ids["outcome"],
            ),
            "late": _artifact(
                sid,
                ids["late"],
                ArtifactKind.EVIDENCE,
                f"Post-decision confirmation: {incident.root_cause}",
                10,
                event_ids["late"],
            ),
        }
        if tier in {DifficultyTier.MEDIUM, DifficultyTier.HARD}:
            artifacts["assumption"] = _artifact(
                sid,
                ids["assumption"],
                ArtifactKind.ASSUMPTION,
                "Decision evidence assumption: the inspected signal remains current",
                11,
                event_ids["constraint"],
            )
        if tier is DifficultyTier.HARD:
            artifacts["risk"] = _artifact(
                sid,
                ids["risk"],
                ArtifactKind.CONSTRAINT,
                "Decision evidence risk: avoid simultaneous changes to healthy dependencies",
                11,
                event_ids["constraint"],
            )
        rows = [
            (10, LedgerOperation.COMMIT, "evidence", None, None, None),
            (11, LedgerOperation.COMMIT, "constraint", None, None, None),
            (12, LedgerOperation.COMMIT, "decision", None, None, None),
            (12, LedgerOperation.LINK, None, "decision", "evidence", RelationKind.SUPPORTS),
            (12, LedgerOperation.LINK, None, "decision", "constraint", RelationKind.SUPPORTS),
            (13, LedgerOperation.COMMIT, "action", None, None, None),
            (13, LedgerOperation.LINK, None, "action", "decision", RelationKind.MOTIVATES),
            (14, LedgerOperation.COMMIT, "outcome", None, None, None),
            (14, LedgerOperation.LINK, None, "outcome", "action", RelationKind.PRODUCES),
            (20, LedgerOperation.COMMIT, "late", None, None, None),
            (20, LedgerOperation.LINK, None, "decision", "late", RelationKind.SUPPORTS),
        ]
        if tier in {DifficultyTier.MEDIUM, DifficultyTier.HARD}:
            rows.insert(2, (11, LedgerOperation.COMMIT, "assumption", None, None, None))
            rows.insert(
                6,
                (
                    12,
                    LedgerOperation.LINK,
                    None,
                    "decision",
                    "assumption",
                    RelationKind.SUPPORTS,
                ),
            )
        if tier is DifficultyTier.HARD:
            rows.insert(3, (11, LedgerOperation.COMMIT, "risk", None, None, None))
            rows.insert(
                8,
                (
                    12,
                    LedgerOperation.LINK,
                    None,
                    "decision",
                    "risk",
                    RelationKind.SUPPORTS,
                ),
            )
        entries = tuple(
            LedgerEntry(
                sequence=index,
                logical_time=time,
                phase={
                    10: ScenarioPhase.ACCUMULATE,
                    11: ScenarioPhase.DECIDE,
                    12: ScenarioPhase.DECIDE,
                    13: ScenarioPhase.EXPERIENCE,
                    14: ScenarioPhase.EXPERIENCE,
                    20: ScenarioPhase.PERTURB,
                }[time],
                operation=operation,
                artifact=artifacts[artifact_name] if artifact_name else None,
                target_id=ids[target] if target else None,
                source_id=ids[source] if source else None,
                relation=relation,
            )
            for index, (time, operation, artifact_name, target, source, relation) in enumerate(rows)
        )
        ledger = WorldLedger(sid, entries)
        scenarios.append(
            Scenario(
                PublicScenario(
                    sid,
                    "decision_lineage",
                    seed,
                    variant,
                    events,
                    max_agent_steps,
                    schema_version=2,
                ),
                EvaluatorSpec(
                    {
                        "decision": artifacts["decision"].content,
                        "outcome": artifacts["outcome"].content,
                    },
                    tuple(
                        ExpectedMemory(
                            ids[name], artifacts[name].kind.value, artifacts[name].content
                        )
                        for name in artifacts
                    ),
                    category="decision_lineage",
                ),
                {
                    "decision_world_schema": 2,
                    "world_ledger": ledger.to_dict(),
                    "decision_ref": ids["decision"],
                    "decision_time": 12,
                    "decision_context_ids": [ids[name] for name in context_names],
                    "late_evidence_ids": [ids["late"]],
                    "action_id": ids["action"],
                    "outcome_id": ids["outcome"],
                    "incident_world": incident.to_dict(),
                    "matched_audit_pair": {
                        "faithful_evidence_ids": [ids[name] for name in context_names],
                        "contaminated_evidence_ids": [
                            *(ids[name] for name in context_names),
                            ids["late"],
                        ],
                    },
                    "difficulty_tier": tier.value,
                    "realization_pattern": f"decision-context-{len(context_names)}",
                },
            )
        )
    return scenarios
