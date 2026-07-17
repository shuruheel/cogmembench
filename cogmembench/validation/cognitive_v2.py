from __future__ import annotations

from typing import Any

from ..agents import (
    CognitiveVerticalSliceExecutor,
    DecisionLineageOracleExecutor,
    RecursiveInvestigationOracleExecutor,
)
from ..evaluators import (
    evaluate_cognitive_v2,
    evaluate_decision_lineage_v2,
    evaluate_recursive_v2,
)
from ..scenarios.schema import Scenario
from .generator_validity import validate_scenario_leakage

PRIMARY_CEILING_METRICS = (
    "belief_v_k_accuracy",
    "dependency_invalidation_f1",
    "unaffected_artifact_preservation_rate",
)

FAMILY_VALIDATORS = {
    "bitemporal_belief_revision": (
        CognitiveVerticalSliceExecutor,
        evaluate_cognitive_v2,
        PRIMARY_CEILING_METRICS,
    ),
    "recursive_investigation": (
        RecursiveInvestigationOracleExecutor,
        evaluate_recursive_v2,
        (
            "trace_verified_reuse_accuracy",
            "conclusion_revision_accuracy",
            "trace_verified_repaired_reuse_accuracy",
            "failure_amplification_avoided",
            "execution_success",
            "true_world_correctness",
        ),
    ),
    "decision_lineage": (
        DecisionLineageOracleExecutor,
        evaluate_decision_lineage_v2,
        (
            "decision_time_context_reconstruction_f1",
            "audit_faithfulness",
            "decision_rationality",
        ),
    ),
}


def validate_cognitive_v2_scenarios(scenarios: list[Scenario]) -> dict[str, Any]:
    """Replay gold ledgers and require a perfect mechanically derived oracle ceiling."""
    if not scenarios:
        raise ValueError("at least one scenario is required")
    rows = []
    failures = []
    for scenario in scenarios:
        if scenario.public.family not in FAMILY_VALIDATORS:
            raise ValueError(f"unsupported cognitive-v2 family: {scenario.public.family}")
        executor_type, evaluator, primary_metrics = FAMILY_VALIDATORS[scenario.public.family]
        trial = executor_type().run(scenario)
        evaluation = evaluator(trial, scenario)
        leakage = validate_scenario_leakage(scenario)
        failed_metrics = {
            metric: evaluation["metrics"].get(metric)
            for metric in primary_metrics
            if evaluation["metrics"].get(metric) != 1.0
        }
        row = {
            "scenario_id": scenario.public.scenario_id,
            "family": scenario.public.family,
            "metrics": evaluation["metrics"],
            "phase_count": len(trial.get("phase_trace", scenario.public.events)),
            "temporal_probe_count": len(trial.get("temporal_probe_results", ())),
            "leakage": leakage,
            "passed": not failed_metrics and leakage["passed"],
        }
        rows.append(row)
        if failed_metrics:
            failures.append({"scenario_id": scenario.public.scenario_id, "metrics": failed_metrics})
        if not leakage["passed"]:
            failures.append(
                {
                    "scenario_id": scenario.public.scenario_id,
                    "leakage": leakage,
                }
            )
    return {
        "schema_version": 2,
        "scenarios": len(scenarios),
        "families": sorted({scenario.public.family for scenario in scenarios}),
        "passed": not failures,
        "primary_ceiling_metrics": {
            family: list(FAMILY_VALIDATORS[family][2])
            for family in sorted({scenario.public.family for scenario in scenarios})
        },
        "failures": failures,
        "results": rows,
    }
