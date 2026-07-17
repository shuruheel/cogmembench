from __future__ import annotations

import json
from types import SimpleNamespace

from cogmembench import cli
from cogmembench.agents import TrialExecutor
from cogmembench.evaluators import evaluate_trial, evaluate_trial_v2
from cogmembench.evaluators.deterministic import _value_match
from cogmembench.memory import ReferenceCognitiveMemory
from cogmembench.providers import DeterministicProvider
from cogmembench.reports import aggregate_results, compare_repetitions, render_report
from cogmembench.scenarios.generators import generate_development_v2, generate_suite
from cogmembench.telemetry import EventLog
from cogmembench.telemetry.tokens import count_tokens
from cogmembench.trajectory import export_trajectories


def test_deterministic_evaluator_scores_correct_answer(tmp_path):
    scenario = generate_suite("smoke", 42, 1, [42], 8)[0]
    log = EventLog(tmp_path / "eval.jsonl")
    trial = TrialExecutor(DeterministicProvider(), "mindgraph-passive", log, memory=ReferenceCognitiveMemory()).run(scenario.public)
    evaluation = evaluate_trial(trial, scenario, log.events)
    assert evaluation["metrics"]["task_success"] == 1
    assert evaluation["metrics"]["memory_recall"] > 0


def test_metric_aggregation_and_report_are_reproducible():
    row = {
        "scenario_id": "x",
        "condition": "stateless",
        "answer": "{}",
        "metrics": {"input_tokens": 10, "model_calls": 1},
        "evaluation": {"metrics": {"task_success": 0.5, "memory_contamination": 0.0}},
    }
    weights = {"task_success": 0.9, "inverse_memory_contamination": 0.1}
    a = aggregate_results([row], weights)
    b = aggregate_results([row], weights)
    assert a == b
    manifest = {"run_id": "r", "generated_at": "now", "scale": "smoke", "model": "m", "provider": "p", "backend": "reference", "token_accounting": "fallback", "scenario_count": 1, "completed_trials": 1, "base_seed": 42, "conditions": ["stateless"]}
    assert render_report(a, manifest) == render_report(b, manifest)


def test_evaluation_loads_latest_raw_retry_even_when_evaluated_artifact_exists(
    tmp_path, monkeypatch
):
    results = tmp_path / "results"
    (results / "raw").mkdir(parents=True)
    (results / "evaluated").mkdir(parents=True)
    manifest = {"run_id": "retry"}
    (results / "raw" / "retry.manifest.json").write_text(json.dumps(manifest))
    failed = {"trial_id": "trial", "valid": False, "error": "rate limited"}
    recovered = {"trial_id": "trial", "valid": True, "answer": "recovered"}
    (results / "raw" / "retry.jsonl").write_text(
        json.dumps(failed) + "\n" + json.dumps(recovered) + "\n"
    )
    (results / "evaluated" / "retry.jsonl").write_text(json.dumps(failed) + "\n")
    monkeypatch.setattr(cli, "ROOT", tmp_path)

    raw_rows, _ = cli._load_run("retry", prefer_evaluated=False)
    evaluated_rows, _ = cli._load_run("retry")

    assert raw_rows == [recovered]
    assert evaluated_rows == [failed]


def test_repetition_comparison_keeps_model_and_run_variance_separate():
    def run(model, run_id, passive, active):
        rows = []
        for condition, score in (("stateless", 0.0), ("mindgraph-passive", passive), ("mindgraph-active-prefetch", active)):
            rows.append(
                {
                    "scenario_id": "scenario",
                    "condition": condition,
                    "valid": True,
                    "metrics": {"input_tokens": 10},
                    "evaluation": {"metrics": {"task_success": score}},
                }
            )
        return ({"model": model, "run_id": run_id}, rows)

    comparison = compare_repetitions(
        [
            run("strong", "s1", 0.4, 0.8),
            run("strong", "s2", 0.6, 1.0),
            run("open", "o1", 0.4, 0.3),
            run("open", "o2", 0.6, 0.5),
        ],
        {"task_success": 1.0},
    )

    strong = comparison["models"]["strong"]
    assert strong["conditions"]["mindgraph-active-prefetch"]["trials"] == 2
    assert strong["conditions"]["mindgraph-active-prefetch"]["metrics_across_repetitions"]["task_success"]["mean"] == 0.9
    assert strong["contrasts"]["mindgraph-active-prefetch_minus_mindgraph-passive"]["absolute"]["mean"] == 0.4
    assert comparison["model_interaction"]["mindgraph-active-prefetch"]["task_success_difference"] == -0.5


def test_token_counter_is_stable():
    assert count_tokens("alpha, beta!") == 4
    assert count_tokens("alpha, beta!") == count_tokens("alpha, beta!")


def test_trajectory_export_does_not_invent_step_labels(tmp_path):
    results = tmp_path / "results"
    (results / "raw").mkdir(parents=True)
    (results / "traces").mkdir(parents=True)
    (results / "raw" / "r.jsonl").write_text(
        json.dumps(
            {
                "scenario_id": "s",
                "condition": "mindgraph-active-pull",
                "evaluation": {
                    "metrics": {
                        "task_success": 1.0,
                        "memory_precision": 0.5,
                        "correct_primitive_selection": 1.0,
                    }
                },
            }
        )
        + "\n"
    )
    (results / "traces" / "r.jsonl").write_text(
        json.dumps(
            {
                "event_type": "tool_call",
                "condition": "mindgraph-active-pull",
                "scenario_id": "s",
                "payload": {
                    "tool": "mindgraph_retrieve",
                    "arguments": {},
                    "observation": {"hits": []},
                },
            }
        )
        + "\n"
    )
    exported = export_trajectories("r", tmp_path)
    row = json.loads(exported.read_text())
    assert row["evaluation"]["useful"] is None
    assert row["evaluation"]["primitive_correct"] is None
    assert row["evaluation"]["annotation_status"] == "pending_step_review"
    assert row["evaluation"]["trial_metrics"]["task_success"] == 1.0
    assert row["graph_delta"] == {}


def test_deterministic_equivalence_is_semantic_but_not_overbroad():
    assert _value_match("March 19, 2026", "March 19")
    assert _value_match("United States", "US")
    assert _value_match("fixed-width binary decoding", "fixed-width binary decoder")
    assert _value_match("updated preference", "corrected preference")
    assert _value_match(
        "Latest preference update supersedes the earlier train preference",
        "corrected preference",
    )
    assert _value_match(
        "Traveler now prefers rental car instead of train",
        "corrected preference",
    )
    assert _value_match(
        "Do not retry parsing until schema-v2 validation is in place",
        "parse without schema",
    )
    assert _value_match(
        "Decode the fixed-width header using byte offsets",
        "fixed-width binary decoder",
    )
    assert _value_match(
        "The lesson applies to quoted delimited exports; the fixed-width control uses offsets",
        "delimited text only",
    )
    assert _value_match(
        "Delimited text with quoting; not applicable to fixed-width binary data",
        "delimited text only",
    )
    assert _value_match("robust quoted-delimited parser", "CSV parser")
    assert not _value_match("CSV parser", "quoted pipe-delimited parser")
    assert _value_match(
        "manual splitting fails when quoted fields contain delimiters",
        "quoted delimiter",
    )
    assert not _value_match("car", "rental car")
    assert not _value_match("delimited text and binary", "delimited text only")


def test_failure_scenario_advertises_a_compatible_parser():
    scenario = next(
        item
        for item in generate_suite("smoke", 42, 1, [42], 8)
        if item.public.family == "failure_learning"
    )
    prompt = "\n".join(event.content for event in scenario.public.events)
    assert "splitting every line on comma" in prompt
    assert "robust CSV parser is available" in prompt
    assert scenario.evaluator.expected_answer["similar_method"] == "CSV parser"


def test_development_v2_scopes_category_and_memory_metrics():
    scenario = generate_development_v2(42)[10]
    answers = {
        checkpoint: json.dumps(expected)
        for checkpoint, expected in scenario.evaluator.expected_answers.items()
    }
    trial = {
        "scenario_id": scenario.public.scenario_id,
        "condition": "transcript",
        "answer": answers[next(reversed(answers))],
        "answers": answers,
        "metrics": {"read_context_tokens": 100, "lifecycle_tokens": 1000},
        "memory_snapshot": {"records": []},
    }
    result = evaluate_trial_v2(trial, scenario, [])

    assert result["metrics"]["task_success"] == 1.0
    assert result["metrics"]["belief_update_accuracy"] == 1.0
    assert result["metrics"]["contradiction_handling"] == 1.0
    assert result["metrics"]["continuity_accuracy"] is None
    assert result["metrics"]["long_horizon_recovery"] is None
    assert result["metrics"]["memory_precision"] is None
    assert result["metrics"]["memory_recall"] is None
    assert len(result["reuse_curve"]) == 2


def test_infrastructure_nodes_do_not_reduce_memory_precision():
    scenario = generate_suite("smoke", 42, 1, [42], 8)[0]
    expected = scenario.evaluator.durable[0]
    trial = {
        "answer": "{}",
        "memory_snapshot": {
            "records": [
                {"uid": "pref", "node_type": "Preference", "summary": expected.text},
                {"uid": "chunk", "node_type": "Chunk", "summary": expected.text},
            ]
        },
    }
    result = evaluate_trial(trial, scenario, [])
    assert result["metrics"]["memory_precision"] == 1.0


def test_one_record_cannot_satisfy_multiple_expected_memories():
    scenario = generate_suite("smoke", 42, 1, [42], 8)[0]
    combined = " ".join(item.text for item in scenario.evaluator.durable)
    trial = {
        "answer": "{}",
        "memory_snapshot": {
            "records": [{"uid": "one", "node_type": "Preference", "summary": combined}]
        },
    }
    result = evaluate_trial(trial, scenario, [])
    assert result["metrics"]["memory_recall"] == 1 / 3
    assert len(result["matched_memory_ids"]) == 1


def test_supersession_requires_exact_new_to_old_relation():
    scenario = generate_suite("smoke", 42, 1, [42], 8)[0]
    records = [
        {
            "uid": item.memory_id,
            "node_type": item.primitive,
            "summary": item.text,
        }
        for item in scenario.evaluator.durable
    ]
    new = next(item for item in scenario.evaluator.durable if item.supersedes)
    unrelated = next(item for item in scenario.evaluator.durable if item.memory_id != new.supersedes)
    wrong = {
        "answer": "{}",
        "memory_snapshot": {
            "records": records,
            "edges": [
                {
                    "from_uid": unrelated.memory_id,
                    "to_uid": new.supersedes,
                    "edge_type": "Supersedes",
                }
            ],
        },
    }
    right = {
        **wrong,
        "memory_snapshot": {
            "records": records,
            "edges": [
                {
                    "from_uid": new.memory_id,
                    "to_uid": new.supersedes,
                    "edge_type": "Supersedes",
                }
            ],
        },
    }
    assert evaluate_trial(wrong, scenario, [])["metrics"]["supersession_correctness"] == 0
    assert evaluate_trial(right, scenario, [])["metrics"]["supersession_correctness"] == 1


def test_provenance_uses_expected_evidence_edges():
    scenario = generate_suite("smoke", 42, 1, [42], 8)[1]
    records = [
        {"uid": item.memory_id, "node_type": item.primitive, "summary": item.text}
        for item in scenario.evaluator.durable
    ]
    edges = [
        {"from_uid": source, "to_uid": item.memory_id, "edge_type": "Supports"}
        for item in scenario.evaluator.durable
        for source in item.provenance
    ]
    trial = {"answer": "{}", "memory_snapshot": {"records": records, "edges": edges}}
    assert evaluate_trial(trial, scenario, [])["metrics"]["provenance_completeness"] == 1


def test_active_prefetch_is_not_scored_as_missed_explicit_retrieval():
    scenario = generate_suite("smoke", 42, 1, [42], 8)[0]
    expected = next(
        item
        for item in scenario.evaluator.durable
        if item.memory_id in scenario.evaluator.expected_retrieval_ids
    )
    event = SimpleNamespace(
        event_type="retrieval",
        payload={"returned": [{"uid": "hit", "summary": expected.text}]},
    )
    trial = {
        "condition": "mindgraph-active-prefetch",
        "answer": "{}",
        "memory_snapshot": {"records": [], "edges": []},
    }
    metrics = evaluate_trial(trial, scenario, [event])["metrics"]
    assert metrics["appropriate_retrieval_rate"] > 0
    assert metrics["missed_retrieval_rate"] < 1
    assert metrics["unnecessary_retrieval_rate"] == 0
