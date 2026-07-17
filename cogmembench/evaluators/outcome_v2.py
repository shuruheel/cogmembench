from __future__ import annotations

import json
from typing import Any

from ..environments import (
    ActionKind,
    IncidentAction,
    IncidentWorld,
    ServiceIncidentEnvironment,
    execution_score,
)
from ..scenarios.schema import Scenario
from .equivalence import (
    calibration_metrics,
    contains_equivalent_phrase,
    equivalent_value,
    parse_json_object,
    structured_field_accuracy,
)


def _json(answer: str) -> dict[str, Any]:
    return parse_json_object(answer)


def _field_accuracy(answer: str, expected: dict[str, Any]) -> tuple[float, dict[str, bool]]:
    return structured_field_accuracy(answer, expected)


def _aggregate_calibration(
    answers: dict[str, str],
    checkpoint_scores: dict[str, float],
) -> dict[str, float | None]:
    rows = [
        calibration_metrics(answers.get(checkpoint, ""), score)
        for checkpoint, score in checkpoint_scores.items()
    ]
    brier = [float(row["confidence_brier"]) for row in rows if row["confidence_brier"] is not None]
    return {
        "confidence_brier": sum(brier) / len(brier) if brier else None,
        "confidence_mean": (
            sum(
                float(row["confidence_value"])
                for row in rows
                if row["confidence_value"] is not None
            )
            / sum(row["confidence_value"] is not None for row in rows)
            if any(row["confidence_value"] is not None for row in rows)
            else None
        ),
        "confidence_coverage": (
            sum(float(row["confidence_available"] or 0.0) for row in rows) / len(rows)
            if rows
            else 0.0
        ),
        "inappropriate_abstention_rate": (
            sum(float(row["inappropriate_abstention"] or 0.0) for row in rows) / len(rows)
            if rows
            else 0.0
        ),
    }


def _capability_cell(trial: dict[str, Any], capability: str) -> dict[str, Any]:
    manifest = trial.get("capabilities") or {}
    available = bool(manifest.get(capability, False))
    return {
        "available": available,
        "reason": "" if available else f"adapter does not expose {capability}",
    }


def _evaluate_bitemporal(trial: dict[str, Any], scenario: Scenario) -> dict[str, Any]:
    answers = trial.get("answers", {})
    checks: dict[str, Any] = {}
    checkpoint_scores = {}
    for checkpoint, expected in scenario.evaluator.expected_answers.items():
        score, fields = _field_accuracy(answers.get(checkpoint, ""), expected)
        checkpoint_scores[checkpoint] = score
        checks[checkpoint] = fields
    belief = (
        checkpoint_scores.get("current", 0.0) + checkpoint_scores.get("historical", 0.0)
    ) / 2
    repair = checkpoint_scores.get("repair", 0.0)
    calibration = _aggregate_calibration(answers, checkpoint_scores)
    return {
        "track": "outcome",
        "metrics": {
            "current_belief_accuracy": checkpoint_scores.get("current", 0.0),
            "current_state_accuracy": checkpoint_scores.get("current", 0.0),
            "historical_belief_accuracy": checkpoint_scores.get("historical", 0.0),
            "historical_belief_reconstruction": checkpoint_scores.get("historical", 0.0),
            "belief_v_k_accuracy": belief,
            "valid_time_accuracy": belief,
            "known_at_time_accuracy": belief,
            "late_arrival_handling": repair,
            "future_effective_state_handling": checkpoint_scores.get("current", 0.0),
            "repair_accuracy": repair,
            "downstream_repair_accuracy": repair,
            **calibration,
            "task_success": (belief + repair) / 2,
        },
        "checks": checks,
        "instrumented": {
            "audit_export": _capability_cell(trial, "audit_export"),
        },
    }


def _evaluate_recursive(trial: dict[str, Any], scenario: Scenario) -> dict[str, Any]:
    answers = trial.get("answers", {})
    derive, derive_checks = _field_accuracy(
        answers.get("derive", ""), scenario.evaluator.expected_answers["derive"]
    )
    reuse, reuse_checks = _field_accuracy(
        answers.get("reuse", ""), scenario.evaluator.expected_answers["reuse"]
    )
    repair, repair_checks = _field_accuracy(
        answers.get("repair", ""), scenario.evaluator.expected_answers["repair"]
    )
    repaired_reuse, repaired_reuse_checks = _field_accuracy(
        answers.get("reuse_repaired", ""),
        scenario.evaluator.expected_answers["reuse_repaired"],
    )
    control = scenario.hidden_world["rederivability_control"]
    budget = int(control["read_budget_tokens"])
    retrieval = trial.get("retrievals", {}).get("reuse", {})
    context = str(retrieval.get("context", "")).lower()
    expected = scenario.evaluator.expected_answers["derive"]
    semantic_conclusion = all(str(value).lower() in context for value in expected.values())
    context_tokens = int(retrieval.get("context_tokens", 0))
    within_budget = context_tokens <= budget
    trace_verified = float(reuse == 1.0 and semantic_conclusion and within_budget)

    repaired_retrieval = trial.get("retrievals", {}).get("reuse_repaired", {})
    repaired_context = str(repaired_retrieval.get("context", "")).lower()
    corrected_expected = scenario.evaluator.expected_answers["reuse_repaired"]
    semantic_revised_conclusion = all(
        str(value).lower() in repaired_context
        for key, value in corrected_expected.items()
        if key != "basis"
    ) and (
        "superseded_conclusion" in repaired_context
        or "revised failure signature conclusion" in repaired_context
    )
    repaired_context_tokens = int(repaired_retrieval.get("context_tokens", 0))
    repaired_within_budget = repaired_context_tokens <= budget
    repaired_answer = _json(answers.get("reuse_repaired", ""))
    stale_expected = scenario.evaluator.expected_answers["derive"]
    stale_intrusion = float(
        any(
            equivalent_value(repaired_answer.get(key), value)
            for key, value in stale_expected.items()
        )
        or repaired_answer.get("basis") == "stored conclusion"
    )
    trace_verified_repair = float(
        repair == 1.0
        and repaired_reuse == 1.0
        and semantic_revised_conclusion
        and repaired_within_budget
        and not stale_intrusion
    )

    parsed = repaired_answer
    incident = IncidentWorld.from_dict(scenario.hidden_world["corrected_incident_world"])
    environment = ServiceIncidentEnvironment(incident)
    target = str(parsed.get("root_service", ""))
    remediation = str(parsed.get("remediation", ""))
    remediation_is_valid = equivalent_value(remediation, incident.correct_remediation)
    if target in incident.services and remediation_is_valid:
        environment.step(
            IncidentAction(ActionKind.REMEDIATE, target, incident.correct_remediation)
        )
    execution = execution_score(environment)
    calibration = _aggregate_calibration(
        answers,
        {
            "derive": derive,
            "reuse": reuse,
            "repair": repair,
            "reuse_repaired": repaired_reuse,
        },
    )
    return {
        "track": "outcome",
        "metrics": {
            "derivation_accuracy": derive,
            "raw_reuse_accuracy": reuse,
            "trace_verified_reuse_accuracy": trace_verified,
            "conclusion_revision_accuracy": repair,
            "raw_repaired_reuse_accuracy": repaired_reuse,
            "trace_verified_repaired_reuse_accuracy": trace_verified_repair,
            "stale_conclusion_intrusion_rate": stale_intrusion,
            "failure_amplification_avoided": trace_verified_repair,
            "derived_artifact_retrieved": float(semantic_conclusion),
            "intermediate_conclusion_retention": float(semantic_conclusion),
            "reuse_context_within_budget": float(within_budget),
            "execution_success": execution["execution_success"],
            "true_world_correctness": execution["true_world_correctness"],
            "cost_efficiency": execution["cost_efficiency"],
            "unsupported_inference_rate": float(reuse == 1.0 and not semantic_conclusion),
            "reasoning_contamination_rate": max(
                float(reuse == 1.0 and not semantic_conclusion), stale_intrusion
            ),
            "transfer_scope_accuracy": repaired_reuse,
            "recomputation_avoided": trace_verified,
            "recomputation_required": float(not semantic_conclusion),
            **calibration,
            "task_success": (
                trace_verified + trace_verified_repair + execution["execution_success"]
            ) / 3,
        },
        "checks": {
            "derive": derive_checks,
            "reuse": reuse_checks,
            "repair": repair_checks,
            "reuse_repaired": repaired_reuse_checks,
            "semantic_conclusion_in_context": semantic_conclusion,
            "context_tokens": context_tokens,
            "budget_tokens": budget,
            "semantic_revised_conclusion_in_context": semantic_revised_conclusion,
            "repaired_context_tokens": repaired_context_tokens,
            "repaired_context_within_budget": repaired_within_budget,
        },
        "revision_curve": [
            {
                "depth": int(scenario.hidden_world["derivation_depth"]),
                "revision_accuracy": repair,
                "trace_verified_repaired_reuse_accuracy": trace_verified_repair,
                "stale_conclusion_intrusion_rate": stale_intrusion,
            }
        ],
        "execution": execution,
        "instrumented": {
            "audit_export": _capability_cell(trial, "audit_export"),
        },
    }


def _evaluate_decision(trial: dict[str, Any], scenario: Scenario) -> dict[str, Any]:
    answer = _json(trial.get("answers", {}).get("audit", ""))
    incident = IncidentWorld.from_dict(scenario.hidden_world["incident_world"])
    decision_expected = scenario.evaluator.expected_answer["decision"]
    outcome_expected = scenario.evaluator.expected_answer["outcome"]
    decision = str(answer.get("decision", "")).lower()
    action = str(answer.get("action", "")).lower()
    outcome = str(answer.get("outcome", "")).lower()
    evidence = str(answer.get("evidence", "")).lower()
    constraint = str(answer.get("constraint", "")).lower()
    late = incident.root_cause.lower()
    fields = {
        "evidence": contains_equivalent_phrase(evidence, incident.root_signal),
        "constraint": contains_equivalent_phrase(constraint, "minimize user impact"),
        "decision": contains_equivalent_phrase(decision, decision_expected) or (
            incident.root_service in decision
            and contains_equivalent_phrase(decision, incident.correct_remediation)
        ),
        "action": incident.root_service in action
        and contains_equivalent_phrase(action, incident.correct_remediation),
        "outcome": contains_equivalent_phrase(outcome, outcome_expected)
        or (
            any(term in outcome for term in ("resolved", "fixed"))
            and any(term in outcome for term in ("recovered", "healthy"))
        ),
    }
    lineage = sum(fields.values()) / len(fields)
    leakage = float(late in json.dumps(answer).lower())
    exclusion_claim = answer.get("later_evidence_excluded") is True
    faithfulness = lineage * (1.0 - leakage) * float(exclusion_claim)
    environment = ServiceIncidentEnvironment(incident)
    if fields["action"]:
        environment.step(
            IncidentAction(
                ActionKind.REMEDIATE,
                incident.root_service,
                incident.correct_remediation,
            )
        )
    execution = execution_score(environment)
    calibration = calibration_metrics(
        trial.get("answers", {}).get("audit", ""),
        faithfulness,
    )
    return {
        "track": "outcome",
        "metrics": {
            "decision_lineage_field_accuracy": lineage,
            "evidence_to_claim_lineage_f1": float(fields["evidence"] and fields["constraint"]),
            "claim_to_decision_lineage_f1": float(fields["decision"]),
            "post_hoc_evidence_leakage_rate": leakage,
            "audit_faithfulness": faithfulness,
            "counterfactual_rationale_fidelity": faithfulness,
            "decision_rationality": float(fields["decision"] and fields["evidence"]),
            "decision_correctness": float(fields["decision"]),
            "outcome_quality": float(fields["outcome"]),
            "constraint_satisfaction": float(fields["constraint"]),
            "source_attribution_accuracy": float(fields["evidence"]),
            "temporal_provenance_completeness": float(exclusion_claim and not leakage),
            "minimal_support_set_accuracy": float(exclusion_claim and not leakage),
            "replay_reconstruction_success": faithfulness,
            "duplicate_or_invalid_action_rate": float(not fields["action"]),
            "execution_success": execution["execution_success"],
            "confidence_brier": calibration["confidence_brier"],
            "confidence_coverage": calibration["confidence_available"],
            "inappropriate_abstention_rate": calibration["inappropriate_abstention"],
            "task_success": (faithfulness + execution["execution_success"]) / 2,
        },
        "checks": {**fields, "later_evidence_excluded": exclusion_claim},
        "execution": execution,
        "instrumented": {
            "audit_export": _capability_cell(trial, "audit_export"),
        },
    }


def evaluate_outcome_v2(trial: dict[str, Any], scenario: Scenario) -> dict[str, Any]:
    """Score model-visible outcomes without assuming backend-internal instrumentation."""
    evaluators = {
        "bitemporal_belief_revision": _evaluate_bitemporal,
        "recursive_investigation": _evaluate_recursive,
        "decision_lineage": _evaluate_decision,
    }
    try:
        evaluator = evaluators[scenario.public.family]
    except KeyError as exc:
        raise ValueError(f"unsupported cognitive-v2 family: {scenario.public.family}") from exc
    result = evaluator(trial, scenario)
    result["metrics"].update(_policy_metrics(trial, scenario))
    result["metrics"].update(_efficiency_metrics(trial, result["metrics"], scenario.public.family))
    return result


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _policy_metrics(
    trial: dict[str, Any], scenario: Scenario
) -> dict[str, float | int | None]:
    snapshot = trial.get("snapshot")
    if not isinstance(snapshot, dict):
        return {
            "write_appropriateness_precision": None,
            "write_appropriateness_recall": None,
            "write_appropriateness_f1": None,
            "retrieval_appropriateness_precision": None,
            "retrieval_appropriateness_recall": None,
            "retrieval_appropriateness_f1": None,
            "retrieval_opportunity_coverage": None,
        }

    expected = [row.text.lower() for row in scenario.evaluator.durable]

    def relevant(content: str) -> bool:
        lowered = content.lower()
        if not lowered.strip():
            return False
        return any(
            contains_equivalent_phrase(lowered, value)
            or contains_equivalent_phrase(value, lowered)
            for value in expected
        )

    actual_artifacts = [
        row for row in snapshot.get("artifacts", []) if isinstance(row, dict)
    ]
    relevant_writes = sum(
        relevant(str(row.get("content", ""))) for row in actual_artifacts
    )
    matched_expected = sum(
        any(
            bool((content := str(row.get("content", "")).lower()).strip())
            and (
                contains_equivalent_phrase(content, value)
                or contains_equivalent_phrase(value, content)
            )
            for row in actual_artifacts
        )
        for value in expected
    )
    write_precision = relevant_writes / len(actual_artifacts) if actual_artifacts else 0.0
    write_recall = matched_expected / len(expected) if expected else 1.0

    retrievals = trial.get("retrievals", {})
    retrieval_rows = [
        row
        for value in retrievals.values()
        if isinstance(value, dict)
        for row in value.get("items", [])
        if isinstance(row, dict)
    ] if isinstance(retrievals, dict) else []
    relevant_retrievals = sum(
        relevant(str(row.get("content", ""))) for row in retrieval_rows
    )
    retrieval_precision = (
        relevant_retrievals / len(retrieval_rows) if retrieval_rows else 0.0
    )
    evaluated_checkpoints = sum(event.evaluate for event in scenario.public.events)
    covered_checkpoints = sum(
        any(
            isinstance(row, dict) and relevant(str(row.get("content", "")))
            for row in value.get("items", [])
        )
        for value in retrievals.values()
        if isinstance(value, dict)
    ) if isinstance(retrievals, dict) else 0
    retrieval_recall = (
        covered_checkpoints / evaluated_checkpoints if evaluated_checkpoints else 1.0
    )
    return {
        "write_appropriateness_precision": write_precision,
        "write_appropriateness_recall": write_recall,
        "write_appropriateness_f1": _f1(write_precision, write_recall),
        "retrieval_appropriateness_precision": retrieval_precision,
        "retrieval_appropriateness_recall": retrieval_recall,
        "retrieval_appropriateness_f1": _f1(retrieval_precision, retrieval_recall),
        "retrieval_opportunity_coverage": retrieval_recall,
    }


def _efficiency_metrics(
    trial: dict[str, Any], metrics: dict[str, Any], family: str
) -> dict[str, float | None]:
    usage = trial.get("metrics", {})

    def number(key: str) -> float | None:
        value = usage.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)

    task_success = float(metrics.get("task_success", 0.0))
    lifecycle_tokens = number("lifecycle_tokens")
    if lifecycle_tokens is None:
        inputs, outputs, construction = (
            number("input_tokens"),
            number("output_tokens"),
            number("memory_construction_tokens"),
        )
        lifecycle_tokens = (
            inputs + outputs + construction
            if inputs is not None and outputs is not None and construction is not None
            else None
        )
    read_tokens = number("read_context_tokens")
    inference = number("estimated_inference_cost_usd")
    embedding = number("estimated_embedding_cost_usd")
    substrate = number("estimated_substrate_cost_usd")
    total_cost = (
        inference + embedding + substrate
        if inference is not None and embedding is not None and substrate is not None
        else None
    )
    correct_recursive_steps = None
    if family == "recursive_investigation":
        correct_recursive_steps = sum(
            float(metrics.get(key, 0.0))
            for key in (
                "derivation_accuracy",
                "trace_verified_reuse_accuracy",
                "conclusion_revision_accuracy",
                "trace_verified_repaired_reuse_accuracy",
            )
        )
    audit_success = metrics.get("audit_faithfulness")
    return {
        "lifecycle_tokens": lifecycle_tokens,
        "memory_construction_tokens": number("memory_construction_tokens"),
        "read_context_tokens": read_tokens,
        "model_calls": number("model_calls"),
        "embedding_calls": number("embedding_calls"),
        "memory_storage_growth": number("memory_storage_growth"),
        "lifecycle_cost_usd": total_cost,
        "cost_per_successful_task_usd": (
            total_cost / task_success if total_cost is not None and task_success > 0 else None
        ),
        "task_success_per_1k_read_tokens": (
            task_success * 1000 / read_tokens if read_tokens is not None and read_tokens > 0 else None
        ),
        "lifecycle_tokens_per_successful_task": (
            lifecycle_tokens / task_success
            if lifecycle_tokens is not None and task_success > 0
            else None
        ),
        "cost_per_correct_recursive_step_usd": (
            total_cost / correct_recursive_steps
            if total_cost is not None and correct_recursive_steps
            else None
        ),
        "cost_per_correct_audit_usd": (
            total_cost / float(audit_success)
            if total_cost is not None and isinstance(audit_success, (int, float)) and audit_success > 0
            else None
        ),
    }
