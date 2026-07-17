from __future__ import annotations

import hashlib
import random

from ...difficulty import DifficultyTier, difficulty_for_variant
from ...substrate.schema import (
    ArtifactKind,
    CognitiveArtifact,
    EpistemicStatus,
    RelationKind,
    TimeInterval,
    Visibility,
)
from ..schema import Event, EvaluatorSpec, ExpectedMemory, PublicScenario, Scenario
from ..world import (
    CognitiveWorld,
    LedgerEntry,
    LedgerOperation,
    RepairProbe,
    ScenarioPhase,
    TemporalProbe,
    WorldLedger,
)

BITEMPORAL_CASES = (
    {
        "entity": "Orchid API",
        "subject": "enterprise rate limit",
        "scope": "enterprise tier",
        "old": "100 requests/minute",
        "new": "240 requests/minute",
        "old_source": "cached provider guide",
        "new_source": "signed provider bulletin",
        "decision": "cap workers at 90 requests/minute",
        "constraint": "keep retry jitter enabled",
    },
    {
        "entity": "Mosaic logs",
        "subject": "retention period",
        "scope": "audit logs",
        "old": "30 days",
        "new": "90 days",
        "old_source": "draft retention memo",
        "new_source": "approved compliance policy",
        "decision": "delete audit logs after 30 days",
        "constraint": "legal holds override deletion",
    },
    {
        "entity": "Atlas",
        "subject": "US launch date",
        "scope": "United States",
        "old": "March 12",
        "new": "March 21",
        "old_source": "provisional launch calendar",
        "new_source": "authoritative release bulletin",
        "decision": "schedule the launch review for March 11",
        "constraint": "Europe remains unscheduled",
    },
    {
        "entity": "Lumen service",
        "subject": "production owner",
        "scope": "production",
        "old": "Team North",
        "new": "Team East",
        "old_source": "stale service directory",
        "new_source": "signed ownership transfer",
        "decision": "page Team North for production incidents",
        "constraint": "staging remains owned by Team West",
    },
    {
        "entity": "Kestrel filing",
        "subject": "New York deadline",
        "scope": "New York",
        "old": "June 1",
        "new": "June 15",
        "old_source": "preliminary counsel memo",
        "new_source": "regulator correction notice",
        "decision": "submit the filing by May 31",
        "constraint": "California uses a separate deadline",
    },
)


def _instantiate_case(seed: int, variant: int) -> dict[str, str]:
    """Create a seeded bitemporal world with a genuinely distinct corrected fact."""
    rng = random.Random(seed * 2039 + variant)
    case_index = (seed + variant) % len(BITEMPORAL_CASES)
    case = dict(BITEMPORAL_CASES[case_index])
    token = hashlib.sha256(f"bitemporal:{seed}:{variant}".encode()).hexdigest()[:5].upper()
    case["entity"] = f"{case['entity']} {token}"
    case["old_source"] = f"{case['old_source']} revision {rng.randrange(10, 100)}"
    case["new_source"] = f"{case['new_source']} revision {rng.randrange(100, 1000)}"
    if case_index == 0:
        old = 60 + 10 * rng.randrange(1, 13)
        new = old + 20 + 10 * rng.randrange(1, 13)
        case["old"] = f"{old} requests/minute"
        case["new"] = f"{new} requests/minute"
        case["decision"] = f"cap workers at {max(10, old - 10)} requests/minute"
    elif case_index == 1:
        old = 7 * rng.randrange(2, 9)
        new = old + 7 * rng.randrange(3, 13)
        case["old"] = f"{old} days"
        case["new"] = f"{new} days"
        case["decision"] = f"delete audit logs after {old} days"
    elif case_index in {2, 4}:
        months = ("February", "March", "April", "May", "June", "July", "August")
        month = months[rng.randrange(len(months))]
        old_day = rng.randrange(2, 17)
        new_day = old_day + rng.randrange(3, 12)
        case["old"] = f"{month} {old_day}"
        case["new"] = f"{month} {new_day}"
        if case_index == 2:
            case["decision"] = f"schedule the launch review for {month} {old_day - 1}"
        else:
            case["decision"] = f"submit the filing by {month} {old_day - 1}"
    else:
        colors = ("Amber", "Cobalt", "Iris", "Juniper", "Quartz", "Sable")
        old_team = colors[rng.randrange(len(colors))]
        new_team = colors[(colors.index(old_team) + rng.randrange(1, len(colors))) % len(colors)]
        case["old"] = f"Team {old_team}-{rng.randrange(10, 100)}"
        case["new"] = f"Team {new_team}-{rng.randrange(10, 100)}"
        case["decision"] = f"page {case['old']} for production incidents"
    return case


def _artifact(
    scenario_id: str,
    artifact_id: str,
    kind: ArtifactKind,
    content: str,
    *,
    valid_start: int,
    event_id: str,
    subject_key: str = "",
    answer_value: str = "",
    status: EpistemicStatus = EpistemicStatus.ACCEPTED,
) -> CognitiveArtifact:
    structured = {}
    if subject_key:
        structured["subject_key"] = subject_key
    if answer_value:
        structured["answer_value"] = answer_value
    return CognitiveArtifact(
        artifact_id=artifact_id,
        kind=kind,
        content=content,
        scenario_id=scenario_id,
        valid_time=TimeInterval(valid_start),
        structured_content=structured,
        entity_scope=(subject_key,) if subject_key else (),
        epistemic_status=status,
        actor_id="oracle-generator",
        provenance_event_ids=(event_id,),
        visibility=Visibility.AGENT,
    )


def _events(sid: str, case: dict[str, str], variant: int) -> tuple[Event, ...]:
    tier = difficulty_for_variant(variant)
    event_ids = {
        name: f"{sid}:event:{name}"
        for name in ("old", "decision", "correction", "current", "history", "repair")
    }
    events = [
        Event(
            "s1",
            1,
            "user",
            f"The {case['old_source']} reports {case['entity']}'s {case['subject']} as "
            f"{case['old']} for {case['scope']}, effective at logical time 5.",
            event_time=5,
            report_time=10,
            event_id=event_ids["old"],
            phase=ScenarioPhase.ACCUMULATE.value,
        ),
    ]
    if tier in {DifficultyTier.MEDIUM, DifficultyTier.HARD}:
        events.append(
            Event(
                "s1-control",
                1,
                "user",
                f"Independent control note: {case['constraint']}. This note does not change "
                f"the reported {case['subject']}.",
                event_time=11,
                report_time=11,
                event_id=f"{sid}:event:control-note",
                phase=ScenarioPhase.ACCUMULATE.value,
            )
        )
    if tier is DifficultyTier.HARD:
        events.append(
            Event(
                "s1-context",
                1,
                "user",
                f"Separate operational context: {case['entity']} has a routine review queued. "
                f"It neither changes {case['scope']} nor resolves the reported {case['subject']}.",
                event_time=11,
                report_time=12,
                event_id=f"{sid}:event:context-note",
                phase=ScenarioPhase.ACCUMULATE.value,
            )
        )
    events.extend(
        (
        Event(
            "s2",
            1,
            "user",
            f"Decision based on that report: {case['decision']}. Independent constraint: "
            f"{case['constraint']}.",
            event_time=12,
            report_time=13 if tier is DifficultyTier.HARD else 12,
            event_id=event_ids["decision"],
            phase=ScenarioPhase.DECIDE.value,
        ),
        Event(
            "s3",
            1,
            "user",
            f"Retroactive correction from the {case['new_source']}: the {case['subject']} "
            f"has been {case['new']} for {case['scope']} since logical time 5. The earlier "
            "report is superseded; review decisions that depended on it.",
            event_time=5,
            report_time=20,
            event_id=event_ids["correction"],
            phase=ScenarioPhase.PERTURB.value,
        ),
        Event(
            "s4",
            1,
            "user",
            f"At valid time 5 using knowledge available at time 25, what was "
            f"{case['entity']}'s {case['subject']} for {case['scope']}? Return JSON with "
            "value, scope, knowledge_state, and confidence from 0 to 1.",
            evaluate=True,
            checkpoint_id="current",
            event_time=30,
            report_time=30,
            event_id=event_ids["current"],
            phase=ScenarioPhase.REPAIR.value,
        ),
        Event(
            "s5",
            1,
            "user",
            f"Time travel: at valid time 5 using only knowledge available at time 15, "
            f"what did the agent believe about {case['entity']}'s {case['subject']}? "
            "Return JSON with value, scope, knowledge_state, and confidence from 0 to 1.",
            evaluate=True,
            checkpoint_id="historical",
            event_time=31,
            report_time=31,
            event_id=event_ids["history"],
            phase=ScenarioPhase.TIME_TRAVEL.value,
        ),
        Event(
            "s6",
            1,
            "user",
            "After the correction, identify the dependent decision requiring review and "
            "the independent constraint that must remain preserved. Return JSON with "
            "invalidated, preserved, and confidence from 0 to 1.",
            evaluate=True,
            checkpoint_id="repair",
            event_time=32,
            report_time=32,
            event_id=event_ids["repair"],
            phase=ScenarioPhase.AUDIT.value,
        ),
        )
    )
    return tuple(events)


def _world(
    sid: str,
    case: dict[str, str],
    events: tuple[Event, ...],
) -> tuple[CognitiveWorld, dict[str, str], dict[str, CognitiveArtifact]]:
    subject_key = f"{case['entity']}::{case['subject']}::{case['scope']}"
    events_by_session = {event.session_id: event for event in events}
    old_event = str(events_by_session["s1"].event_id)
    decision_event = str(events_by_session["s2"].event_id)
    correction_event = str(events_by_session["s3"].event_id)
    ids = {
        name: f"{sid}:{name}"
        for name in (
            "evidence-old",
            "claim-old",
            "decision-old",
            "constraint",
            "evidence-new",
            "claim-new",
            "decision-stale",
        )
    }
    artifacts = {
        "evidence-old": _artifact(
            sid,
            ids["evidence-old"],
            ArtifactKind.EVIDENCE,
            case["old_source"],
            valid_start=5,
            event_id=old_event,
        ),
        "claim-old": _artifact(
            sid,
            ids["claim-old"],
            ArtifactKind.CLAIM,
            f"{case['subject']} is {case['old']} for {case['scope']}",
            valid_start=5,
            event_id=old_event,
            subject_key=subject_key,
            answer_value=case["old"],
        ),
        "decision-old": _artifact(
            sid,
            ids["decision-old"],
            ArtifactKind.DECISION,
            case["decision"],
            valid_start=12,
            event_id=decision_event,
        ),
        "constraint": _artifact(
            sid,
            ids["constraint"],
            ArtifactKind.CONSTRAINT,
            case["constraint"],
            valid_start=12,
            event_id=decision_event,
        ),
        "evidence-new": _artifact(
            sid,
            ids["evidence-new"],
            ArtifactKind.EVIDENCE,
            case["new_source"],
            valid_start=5,
            event_id=correction_event,
        ),
        "claim-new": _artifact(
            sid,
            ids["claim-new"],
            ArtifactKind.CLAIM,
            f"{case['subject']} is {case['new']} for {case['scope']}",
            valid_start=5,
            event_id=correction_event,
            subject_key=subject_key,
            answer_value=case["new"],
        ),
        "decision-stale": _artifact(
            sid,
            ids["decision-stale"],
            ArtifactKind.DECISION,
            f"Review required: {case['decision']}",
            valid_start=20,
            event_id=correction_event,
            status=EpistemicStatus.STALE,
        ),
    }
    rows = (
        (10, ScenarioPhase.ACCUMULATE, LedgerOperation.COMMIT, "evidence-old", None, None, None),
        (10, ScenarioPhase.ACCUMULATE, LedgerOperation.COMMIT, "claim-old", None, None, None),
        (
            10,
            ScenarioPhase.ACCUMULATE,
            LedgerOperation.LINK,
            None,
            "claim-old",
            "evidence-old",
            RelationKind.SUPPORTS,
        ),
        (12, ScenarioPhase.DECIDE, LedgerOperation.COMMIT, "decision-old", None, None, None),
        (12, ScenarioPhase.DECIDE, LedgerOperation.COMMIT, "constraint", None, None, None),
        (
            12,
            ScenarioPhase.DECIDE,
            LedgerOperation.LINK,
            None,
            "decision-old",
            "claim-old",
            RelationKind.MOTIVATES,
        ),
        (
            20,
            ScenarioPhase.PERTURB,
            LedgerOperation.REVISE,
            "evidence-new",
            "evidence-old",
            None,
            None,
        ),
        (20, ScenarioPhase.PERTURB, LedgerOperation.REVISE, "claim-new", "claim-old", None, None),
        (
            20,
            ScenarioPhase.REPAIR,
            LedgerOperation.REVISE,
            "decision-stale",
            "decision-old",
            None,
            None,
        ),
        (
            20,
            ScenarioPhase.REPAIR,
            LedgerOperation.LINK,
            None,
            "claim-new",
            "evidence-new",
            RelationKind.SUPPORTS,
        ),
        (
            20,
            ScenarioPhase.REPAIR,
            LedgerOperation.LINK,
            None,
            "decision-old",
            "claim-new",
            RelationKind.INVALIDATES,
        ),
    )
    entries = tuple(
        LedgerEntry(
            sequence=index,
            logical_time=time,
            phase=phase,
            operation=operation,
            artifact=artifacts[artifact_name] if artifact_name else None,
            target_id=ids[target_name] if target_name else None,
            source_id=ids[source_name] if source_name else None,
            relation=relation,
        )
        for index, (
            time,
            phase,
            operation,
            artifact_name,
            target_name,
            source_name,
            relation,
        ) in enumerate(rows)
    )
    world = CognitiveWorld(
        ledger=WorldLedger(sid, entries),
        temporal_probes=(
            TemporalProbe(
                "current",
                "current",
                5,
                25,
                subject_key,
                ids["claim-new"],
                case["new"],
            ),
            TemporalProbe(
                "historical",
                "historical",
                5,
                15,
                subject_key,
                ids["claim-old"],
                case["old"],
            ),
        ),
        repair_probe=RepairProbe(
            "repair",
            "repair",
            25,
            (ids["decision-old"],),
            (ids["constraint"],),
        ),
    )
    if any(event.event_id is None for event in events):
        raise AssertionError("generated events must have stable IDs")
    return world, ids, artifacts


def generate_bitemporal_belief_revision(
    seed: int,
    max_agent_steps: int = 8,
    variants: int = 5,
) -> list[Scenario]:
    if variants <= 0:
        raise ValueError("variants must be positive")
    scenarios = []
    for variant in range(variants):
        case = _instantiate_case(seed, variant)
        tier = difficulty_for_variant(variant)
        sid = f"bitemporal-{seed}-{variant:02d}"
        events = _events(sid, case, variant)
        world, ids, artifacts = _world(sid, case, events)
        expected_answers = {
            "current": {
                "value": case["new"],
                "scope": case["scope"],
                "knowledge_state": "corrected",
            },
            "historical": {
                "value": case["old"],
                "scope": case["scope"],
                "knowledge_state": "provisional",
            },
            "repair": {
                "invalidated": case["decision"],
                "preserved": case["constraint"],
            },
        }
        durable = (
            ExpectedMemory(
                ids["claim-old"],
                "claim",
                artifacts["claim-old"].content,
                source_session="s1",
            ),
            ExpectedMemory(
                ids["claim-new"],
                "claim",
                artifacts["claim-new"].content,
                source_session="s3",
                supersedes=ids["claim-old"],
            ),
            ExpectedMemory(
                ids["decision-old"],
                "decision",
                artifacts["decision-old"].content,
                source_session="s2",
            ),
            ExpectedMemory(
                ids["constraint"],
                "constraint",
                artifacts["constraint"].content,
                source_session="s2",
            ),
        )
        hidden_world = world.to_hidden_world()
        hidden_world.update(
            {
                "difficulty_tier": tier.value,
                "realization_pattern": {
                    DifficultyTier.EASY: "minimal-revision",
                    DifficultyTier.MEDIUM: "controlled-revision",
                    DifficultyTier.HARD: "distractor-rich-revision",
                }[tier],
            }
        )
        scenarios.append(
            Scenario(
                PublicScenario(
                    sid,
                    "bitemporal_belief_revision",
                    seed,
                    variant,
                    events,
                    max_agent_steps,
                    schema_version=2,
                ),
                EvaluatorSpec(
                    expected_answers["repair"],
                    durable,
                    expected_answers=expected_answers,
                    category="bitemporal_revision",
                ),
                hidden_world,
            )
        )
    return scenarios
