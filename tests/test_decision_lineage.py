from __future__ import annotations

from cogmembench.agents import DecisionLineageOracleExecutor
from cogmembench.evaluators import evaluate_decision_lineage_v2
from cogmembench.scenarios.generators import generate_decision_lineage


def test_decision_lineage_generator_mints_matched_faithful_and_contaminated_pairs():
    scenarios = generate_decision_lineage(42)

    assert len(scenarios) == 5
    for scenario in scenarios:
        pair = scenario.hidden_world["matched_audit_pair"]
        faithful = set(pair["faithful_evidence_ids"])
        contaminated = set(pair["contaminated_evidence_ids"])
        assert faithful < contaminated
        assert contaminated - faithful == set(scenario.hidden_world["late_evidence_ids"])


def test_decision_lineage_oracle_is_faithful_to_decision_time_trace():
    scenario = generate_decision_lineage(42, variants=1)[0]

    trial = DecisionLineageOracleExecutor().run(scenario)
    evaluation = evaluate_decision_lineage_v2(trial, scenario)

    assert evaluation["metrics"]["decision_time_context_trace_f1"] == 1.0
    assert evaluation["metrics"]["decision_time_context_reconstruction_f1"] == 1.0
    assert evaluation["metrics"]["post_hoc_evidence_leakage_rate"] == 0.0
    assert evaluation["metrics"]["audit_faithfulness"] == 1.0
    assert evaluation["metrics"]["decision_rationality"] == 1.0
    assert evaluation["metrics"]["task_success"] == 1.0


def test_post_decision_evidence_in_audit_receipt_is_scored_as_leakage():
    scenario = generate_decision_lineage(42, variants=1)[0]
    trial = DecisionLineageOracleExecutor().run(scenario)
    late_id = scenario.hidden_world["late_evidence_ids"][0]
    trial["audit_receipt"]["evidence_ids"] = tuple(trial["audit_receipt"]["evidence_ids"]) + (
        late_id,
    )

    evaluation = evaluate_decision_lineage_v2(trial, scenario)

    assert evaluation["metrics"]["post_hoc_evidence_leakage_rate"] == 1.0
    assert evaluation["metrics"]["audit_faithfulness"] == 0.0
    assert late_id in evaluation["checks"]["leaked_post_decision_ids"]


def test_decision_difficulty_tiers_raise_contemporaneous_context_burden():
    scenarios = generate_decision_lineage(42, variants=3)

    assert [row.hidden_world["difficulty_tier"] for row in scenarios] == [
        "easy",
        "medium",
        "hard",
    ]
    assert [len(row.hidden_world["decision_context_ids"]) for row in scenarios] == [2, 3, 4]
