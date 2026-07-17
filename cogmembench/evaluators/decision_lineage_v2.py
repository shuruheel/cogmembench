from __future__ import annotations

from typing import Any

from ..scenarios.schema import Scenario


def _f1(expected: set[str], actual: set[str]) -> tuple[float, float, float]:
    true_positive = len(expected & actual)
    precision = true_positive / len(actual) if actual else 0.0
    recall = true_positive / len(expected) if expected else 0.0
    score = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, score


def evaluate_decision_lineage_v2(trial: dict[str, Any], scenario: Scenario) -> dict[str, Any]:
    hidden = scenario.hidden_world
    expected_context = set(hidden["decision_context_ids"])
    late_evidence = set(hidden["late_evidence_ids"])
    trace = trial.get("decision_trace", {})
    receipt = trial.get("audit_receipt", {})
    traced_ids = set(trace.get("retrieved_artifact_ids", ()))
    receipt_ids = set(receipt.get("evidence_ids", ())) | set(
        receipt.get("retrieved_artifact_ids", ())
    )
    trace_precision, trace_recall, trace_f1 = _f1(expected_context, traced_ids)
    receipt_precision, receipt_recall, receipt_f1 = _f1(expected_context, receipt_ids)
    leaked_ids = receipt_ids & late_evidence
    leakage_rate = len(leaked_ids) / len(late_evidence) if late_evidence else 0.0
    decision_time_correct = (
        trace.get("decision_time") == hidden["decision_time"]
        and receipt.get("decision_time") == hidden["decision_time"]
    )
    retrieval_times = tuple(receipt.get("retrieval_times", ()))
    temporal_provenance = bool(
        decision_time_correct
        and retrieval_times
        and all(int(value) <= int(hidden["decision_time"]) for value in retrieval_times)
    )
    minimal_support_set = receipt_ids == expected_context
    execution = trial.get("execution", {})
    rationality = float(
        decision_time_correct
        and trace_f1 == 1.0
        and float(execution.get("true_world_correctness", 0.0)) == 1.0
    )
    audit_faithfulness = receipt_f1 * (1.0 - leakage_rate) * float(decision_time_correct)
    return {
        "metrics": {
            "decision_time_context_trace_f1": trace_f1,
            "decision_time_context_reconstruction_precision": receipt_precision,
            "decision_time_context_reconstruction_recall": receipt_recall,
            "decision_time_context_reconstruction_f1": receipt_f1,
            "post_hoc_evidence_leakage_rate": leakage_rate,
            "audit_faithfulness": audit_faithfulness,
            "decision_rationality": rationality,
            "source_attribution_accuracy": receipt_f1,
            "temporal_provenance_completeness": float(temporal_provenance),
            "minimal_support_set_accuracy": float(minimal_support_set),
            "replay_reconstruction_success": float(
                trace_f1 == 1.0 and receipt_f1 == 1.0 and decision_time_correct
            ),
            "execution_success": float(execution.get("execution_success", 0.0)),
            "task_success": (audit_faithfulness + rationality) / 2,
        },
        "checks": {
            "decision_time_correct": decision_time_correct,
            "expected_context_ids": sorted(expected_context),
            "traced_context_ids": sorted(traced_ids),
            "receipt_context_ids": sorted(receipt_ids),
            "leaked_post_decision_ids": sorted(leaked_ids),
            "trace_precision": trace_precision,
            "trace_recall": trace_recall,
        },
    }
