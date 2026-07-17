from __future__ import annotations

from typing import Any

from ..scenarios.schema import Scenario
from ..scenarios.world import CognitiveWorld


def _f1(expected: set[str], actual: set[str]) -> tuple[float, float, float]:
    if not expected and not actual:
        return 1.0, 1.0, 1.0
    true_positive = len(expected & actual)
    precision = true_positive / len(actual) if actual else 0.0
    recall = true_positive / len(expected) if expected else 0.0
    score = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, score


def evaluate_cognitive_v2(trial: dict[str, Any], scenario: Scenario) -> dict[str, Any]:
    world = CognitiveWorld.from_hidden_world(scenario.hidden_world)
    actual_temporal = {row.get("probe_id"): row for row in trial.get("temporal_probe_results", [])}
    temporal_checks = []
    for probe in world.temporal_probes:
        actual = actual_temporal.get(probe.probe_id, {})
        valid_time_correct = bool(
            actual.get("valid_at") == probe.valid_at and actual.get("selected_valid_at")
        )
        known_at_correct = bool(
            actual.get("known_at") == probe.known_at
            and actual.get("selected_artifact_id") == probe.expected_artifact_id
        )
        value_correct = actual.get("selected_value") == probe.expected_value
        temporal_checks.append(
            {
                "probe_id": probe.probe_id,
                "valid_time_correct": valid_time_correct,
                "known_at_correct": known_at_correct,
                "value_correct": value_correct,
                "belief_v_k_correct": valid_time_correct and known_at_correct and value_correct,
            }
        )

    repair = world.repair_probe
    actual_repair = trial.get("repair_probe_result", {})
    expected_invalidated = set(repair.invalidated_artifact_ids)
    actual_invalidated = set(actual_repair.get("invalidated_artifact_ids", ()))
    precision, recall, invalidation_f1 = _f1(expected_invalidated, actual_invalidated)
    expected_preserved = set(repair.preserved_artifact_ids)
    actual_preserved = set(actual_repair.get("preserved_artifact_ids", ()))
    preservation = (
        len(expected_preserved & actual_preserved) / len(expected_preserved)
        if expected_preserved
        else 1.0
    )
    valid_accuracy = sum(row["valid_time_correct"] for row in temporal_checks) / len(
        temporal_checks
    )
    known_accuracy = sum(row["known_at_correct"] for row in temporal_checks) / len(temporal_checks)
    belief_accuracy = sum(row["belief_v_k_correct"] for row in temporal_checks) / len(
        temporal_checks
    )
    historical_artifact_ids = {
        probe.expected_artifact_id for probe in world.temporal_probes if probe.probe_id != "current"
    }
    current_actual = actual_temporal.get("current", {})
    stale_intrusion = float(
        current_actual.get("selected_artifact_id") in historical_artifact_ids
    )
    snapshot_isolation = float(all(row["belief_v_k_correct"] for row in temporal_checks))
    return {
        "metrics": {
            "belief_valid_time_accuracy": valid_accuracy,
            "belief_known_at_accuracy": known_accuracy,
            "belief_v_k_accuracy": belief_accuracy,
            "dependency_invalidation_precision": precision,
            "dependency_invalidation_recall": recall,
            "dependency_invalidation_f1": invalidation_f1,
            "unaffected_artifact_preservation_rate": preservation,
            "stale_conclusion_intrusion_rate": stale_intrusion,
            "supersession_correctness": snapshot_isolation,
            "snapshot_isolation": snapshot_isolation,
            "downstream_repair_accuracy": invalidation_f1,
            "task_success": (belief_accuracy + invalidation_f1 + preservation) / 3,
        },
        "temporal_checks": temporal_checks,
        "repair_check": {
            "expected_invalidated": sorted(expected_invalidated),
            "actual_invalidated": sorted(actual_invalidated),
            "expected_preserved": sorted(expected_preserved),
            "actual_preserved": sorted(actual_preserved),
        },
    }
