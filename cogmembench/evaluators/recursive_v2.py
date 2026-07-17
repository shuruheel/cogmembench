from __future__ import annotations

from typing import Any

from ..scenarios.derivation import DerivationDAG, DerivationNodeKind, ReDerivabilityControl
from ..scenarios.schema import Scenario
from .equivalence import structured_field_accuracy


def _answer_accuracy(answer: str, expected: dict[str, str]) -> float:
    score, _ = structured_field_accuracy(answer, expected)
    return score


def evaluate_recursive_v2(trial: dict[str, Any], scenario: Scenario) -> dict[str, Any]:
    hidden = scenario.hidden_world
    dag = DerivationDAG.from_dict(hidden["derivation_dag"])
    control = ReDerivabilityControl.from_dict(hidden["rederivability_control"])
    conclusion_id = str(hidden["required_reuse_artifact_id"])
    revised_conclusion_id = str(hidden["required_repaired_reuse_artifact_id"])
    premise_ids = {
        node.artifact_id for node in dag.nodes if node.kind is DerivationNodeKind.PREMISE
    }
    answers = trial.get("answers", {})
    derive_accuracy = _answer_accuracy(
        answers.get("derive", ""), scenario.evaluator.expected_answers["derive"]
    )
    reuse_accuracy = _answer_accuracy(
        answers.get("reuse", ""), scenario.evaluator.expected_answers["reuse"]
    )
    repair_accuracy = _answer_accuracy(
        answers.get("repair", ""), scenario.evaluator.expected_answers["repair"]
    )
    repaired_reuse_accuracy = _answer_accuracy(
        answers.get("reuse_repaired", ""),
        scenario.evaluator.expected_answers["reuse_repaired"],
    )
    context_ids = set(trial.get("decision_context_artifact_ids", ()))
    conclusion_retrieved = conclusion_id in context_ids
    raw_ancestors_retrieved = len(context_ids & premise_ids)
    retrieval_precision = float(conclusion_retrieved) / len(context_ids) if context_ids else 0.0
    retrieval_recall = float(conclusion_retrieved)
    within_budget = int(trial.get("decision_context_tokens", 0)) <= control.read_budget_tokens
    reuse_dependent_success = float(
        reuse_accuracy == 1.0 and conclusion_retrieved and within_budget
    )
    repaired_context_ids = set(trial.get("repaired_decision_context_artifact_ids", ()))
    revised_conclusion_retrieved = revised_conclusion_id in repaired_context_ids
    stale_conclusion_intrusion = float(conclusion_id in repaired_context_ids)
    repaired_within_budget = (
        int(trial.get("repaired_decision_context_tokens", 0)) <= control.read_budget_tokens
    )
    revision_success = float(
        repair_accuracy == 1.0
        and repaired_reuse_accuracy == 1.0
        and revised_conclusion_retrieved
        and not stale_conclusion_intrusion
        and repaired_within_budget
    )
    execution = trial.get("execution", {})
    execution_success = float(execution.get("execution_success", 0.0))
    depth = int(hidden["derivation_depth"])
    return {
        "metrics": {
            "derivation_accuracy": derive_accuracy,
            "raw_reuse_accuracy": reuse_accuracy,
            "trace_verified_reuse_accuracy": reuse_dependent_success,
            "conclusion_revision_accuracy": repair_accuracy,
            "raw_repaired_reuse_accuracy": repaired_reuse_accuracy,
            "trace_verified_repaired_reuse_accuracy": revision_success,
            "revised_conclusion_retrieved": float(revised_conclusion_retrieved),
            "stale_conclusion_intrusion_rate": stale_conclusion_intrusion,
            "failure_amplification_avoided": revision_success,
            "derived_artifact_retrieved": float(conclusion_retrieved),
            "raw_ancestor_retrieval_count": float(raw_ancestors_retrieved),
            "retrieval_precision": retrieval_precision,
            "retrieval_recall": retrieval_recall,
            "reuse_context_within_budget": float(within_budget),
            "unsupported_inference_rate": float(
                reuse_accuracy == 1.0 and not conclusion_retrieved
            ),
            "recomputation_avoided": float(
                reuse_dependent_success == 1.0 and raw_ancestors_retrieved == 0
            ),
            "execution_success": execution_success,
            "true_world_correctness": float(execution.get("true_world_correctness", 0.0)),
            "cost_efficiency": float(execution.get("cost_efficiency", 0.0)),
            "task_success": (
                reuse_dependent_success + revision_success + execution_success
            ) / 3,
        },
        "depth_curve": [
            {
                "depth": depth,
                "breadth": int(hidden["derivation_breadth"]),
                "raw_accuracy": reuse_accuracy,
                "trace_verified_accuracy": reuse_dependent_success,
            }
        ],
        "revision_curve": [
            {
                "depth": depth,
                "revision_accuracy": repair_accuracy,
                "raw_repaired_reuse_accuracy": repaired_reuse_accuracy,
                "trace_verified_repaired_reuse_accuracy": revision_success,
                "stale_conclusion_intrusion_rate": stale_conclusion_intrusion,
            }
        ],
        "reuse_trace": {
            "required_conclusion_id": conclusion_id,
            "context_artifact_ids": sorted(context_ids),
            "raw_ancestor_ids_in_context": sorted(context_ids & premise_ids),
            "budget_tokens": control.read_budget_tokens,
            "actual_context_tokens": int(trial.get("decision_context_tokens", 0)),
        },
        "repair_trace": {
            "stale_conclusion_id": conclusion_id,
            "required_revised_conclusion_id": revised_conclusion_id,
            "context_artifact_ids": sorted(repaired_context_ids),
            "budget_tokens": control.read_budget_tokens,
            "actual_context_tokens": int(
                trial.get("repaired_decision_context_tokens", 0)
            ),
        },
    }
