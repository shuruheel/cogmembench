from __future__ import annotations

from cogmembench.agents import RecursiveInvestigationOracleExecutor
from cogmembench.evaluators import evaluate_recursive_v2
from cogmembench.scenarios.generators import generate_recursive_investigation


def test_recursive_oracle_ceiling_is_trace_verified_and_executes_remediation():
    scenario = generate_recursive_investigation(42, variants=1)[0]

    trial = RecursiveInvestigationOracleExecutor().run(scenario)
    evaluation = evaluate_recursive_v2(trial, scenario)

    assert evaluation["metrics"]["derivation_accuracy"] == 1.0
    assert evaluation["metrics"]["raw_reuse_accuracy"] == 1.0
    assert evaluation["metrics"]["trace_verified_reuse_accuracy"] == 1.0
    assert evaluation["metrics"]["conclusion_revision_accuracy"] == 1.0
    assert evaluation["metrics"]["trace_verified_repaired_reuse_accuracy"] == 1.0
    assert evaluation["metrics"]["failure_amplification_avoided"] == 1.0
    assert evaluation["metrics"]["stale_conclusion_intrusion_rate"] == 0.0
    assert evaluation["metrics"]["execution_success"] == 1.0
    assert evaluation["metrics"]["task_success"] == 1.0
    assert evaluation["depth_curve"][0]["depth"] == 3
    assert evaluation["revision_curve"][0]["depth"] == 3


def test_stale_conclusion_retrieval_fails_post_correction_reuse() -> None:
    scenario = generate_recursive_investigation(42, variants=1)[0]
    trial = RecursiveInvestigationOracleExecutor().run(scenario)
    trial["repaired_decision_context_artifact_ids"] = [
        scenario.hidden_world["required_reuse_artifact_id"]
    ]

    evaluation = evaluate_recursive_v2(trial, scenario)

    assert evaluation["metrics"]["stale_conclusion_intrusion_rate"] == 1.0
    assert evaluation["metrics"]["trace_verified_repaired_reuse_accuracy"] == 0.0
    assert evaluation["metrics"]["failure_amplification_avoided"] == 0.0


def test_answer_accuracy_without_conclusion_retrieval_does_not_count_as_recursive_reuse():
    scenario = generate_recursive_investigation(42, variants=1)[0]
    trial = RecursiveInvestigationOracleExecutor().run(scenario)
    trial["decision_context_artifact_ids"] = []

    evaluation = evaluate_recursive_v2(trial, scenario)

    assert evaluation["metrics"]["raw_reuse_accuracy"] == 1.0
    assert evaluation["metrics"]["trace_verified_reuse_accuracy"] == 0.0
    assert evaluation["metrics"]["task_success"] == 2 / 3


def test_reuse_context_over_budget_is_rejected_even_with_correct_artifact():
    scenario = generate_recursive_investigation(42, variants=1)[0]
    trial = RecursiveInvestigationOracleExecutor().run(scenario)
    trial["decision_context_tokens"] = 101

    evaluation = evaluate_recursive_v2(trial, scenario)

    assert evaluation["metrics"]["reuse_context_within_budget"] == 0.0
    assert evaluation["metrics"]["trace_verified_reuse_accuracy"] == 0.0
