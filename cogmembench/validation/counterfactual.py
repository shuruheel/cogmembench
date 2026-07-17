from __future__ import annotations

from collections import Counter
from typing import Any

from ..environments import (
    ActionKind,
    IncidentAction,
    IncidentWorld,
    ServiceIncidentEnvironment,
    execution_score,
)
from ..scenarios.schema import Scenario


def validate_incident_counterfactual(world: IncidentWorld) -> dict[str, Any]:
    """Mechanically verify replay, intervention contrast, and branch isolation."""
    base = ServiceIncidentEnvironment(world)
    baseline_actions = [IncidentAction(ActionKind.INSPECT, world.alert_service)]
    baseline_history = base.replay(baseline_actions)
    snapshot = base.snapshot()

    correct = base.branch(snapshot)
    correct.step(
        IncidentAction(
            ActionKind.REMEDIATE,
            world.root_service,
            world.correct_remediation,
        )
    )

    wrong_detail = base.branch(snapshot)
    wrong_detail.step(
        IncidentAction(
            ActionKind.REMEDIATE,
            world.root_service,
            world.distractor_remediations[0],
        )
    )

    wrong_target = next(service for service in world.services if service != world.root_service)
    wrong_location = base.branch(snapshot)
    wrong_location.step(
        IncidentAction(
            ActionKind.REMEDIATE,
            wrong_target,
            world.correct_remediation,
        )
    )

    replay = ServiceIncidentEnvironment(world).replay(baseline_actions)
    restored = base.branch(snapshot).snapshot()
    checks = {
        "correct_intervention_resolves": correct.resolved,
        "wrong_remediation_does_not_resolve": not wrong_detail.resolved,
        "wrong_target_does_not_resolve": not wrong_location.resolved,
        "counterfactual_outcomes_diverge": (
            correct.resolved != wrong_detail.resolved
            and correct.resolved != wrong_location.resolved
        ),
        "base_branch_isolation": base.snapshot() == snapshot,
        "snapshot_restoration": restored == snapshot,
        "replay_determinism": replay == baseline_history,
    }
    return {
        "world_id": world.world_id,
        "difficulty_tier": world.difficulty_tier,
        "realization_pattern": world.realization_pattern,
        "snapshot_id": snapshot.snapshot_id,
        "checks": checks,
        "actual_score": execution_score(correct),
        "wrong_remediation_score": execution_score(wrong_detail),
        "wrong_target_score": execution_score(wrong_location),
        "passed": all(checks.values()),
    }


def validate_counterfactual_oracles(scenarios: list[Scenario]) -> dict[str, Any]:
    """Validate every unique incident-backed cognitive-v2 scenario world."""
    results = []
    seen: set[str] = set()
    for scenario in scenarios:
        for world_role, key in (
            ("initial", "incident_world"),
            ("corrected", "corrected_incident_world"),
        ):
            payload = scenario.hidden_world.get(key)
            if not payload:
                continue
            world = IncidentWorld.from_dict(payload)
            if world.world_id in seen:
                continue
            seen.add(world.world_id)
            result = validate_incident_counterfactual(world)
            result["family"] = scenario.public.family
            result["scenario_id"] = scenario.public.scenario_id
            result["world_role"] = world_role
            results.append(result)
    if not results:
        raise ValueError("counterfactual validation requires incident-backed scenarios")
    tier_counts = Counter(row["difficulty_tier"] for row in results)
    failures = [row for row in results if not row["passed"]]
    return {
        "schema_version": 2,
        "worlds": len(results),
        "difficulty_tiers": dict(sorted(tier_counts.items())),
        "results": results,
        "failures": failures,
        "passed": not failures,
    }
