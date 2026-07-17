from __future__ import annotations

import copy
import json
from typing import Any

from ..agents import (
    CognitiveVerticalSliceExecutor,
    DecisionLineageOracleExecutor,
    RecursiveInvestigationOracleExecutor,
)
from ..environments import IncidentWorld
from ..evaluators import (
    evaluate_cognitive_v2,
    evaluate_decision_lineage_v2,
    evaluate_outcome_v2,
    evaluate_recursive_v2,
)
from ..scenarios.generators import (
    generate_bitemporal_belief_revision,
    generate_decision_lineage,
    generate_recursive_investigation,
)


def _paraphrase_remediation(value: str) -> str:
    replacements = {
        "increase ": "raise ",
        "flush ": "clear ",
        "rotate ": "replace ",
        "restart ": "recycle ",
        "promote ": "fail over to ",
    }
    for prefix, replacement in replacements.items():
        if value.startswith(prefix):
            return replacement + value[len(prefix) :]
    raise ValueError(f"no registered remediation paraphrase for {value!r}")


def _case(
    case_id: str,
    family: str,
    expected: str,
    observed: bool,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "family": family,
        "expected": expected,
        "observed": "accept" if observed else "reject",
        "metrics": metrics,
        "passed": observed == (expected == "accept"),
    }


def validate_evaluator_adversarial_corpus() -> dict[str, Any]:
    """Run matched positive/negative cases through the actual v2 evaluators."""
    cases: list[dict[str, Any]] = []

    bitemporal = generate_bitemporal_belief_revision(42, variants=1)[0]
    bitemporal_gold = CognitiveVerticalSliceExecutor().run(bitemporal)
    gold_evaluation = evaluate_cognitive_v2(bitemporal_gold, bitemporal)
    cases.append(
        _case(
            "bitemporal-gold",
            bitemporal.public.family,
            "accept",
            gold_evaluation["metrics"]["task_success"] == 1.0,
            gold_evaluation["metrics"],
        )
    )
    stale = copy.deepcopy(bitemporal_gold)
    stale["temporal_probe_results"][0]["selected_artifact_id"] = stale[
        "temporal_probe_results"
    ][1]["selected_artifact_id"]
    stale["temporal_probe_results"][0]["selected_value"] = stale["temporal_probe_results"][1][
        "selected_value"
    ]
    stale_evaluation = evaluate_cognitive_v2(stale, bitemporal)
    cases.append(
        _case(
            "bitemporal-stale-current-belief",
            bitemporal.public.family,
            "reject",
            stale_evaluation["metrics"]["stale_conclusion_intrusion_rate"] == 0.0,
            stale_evaluation["metrics"],
        )
    )

    expected = bitemporal.evaluator.expected_answers
    paraphrased_trial = {
        "answers": {
            "current": json.dumps(
                {
                    "value": f"According to available evidence, likely {expected['current']['value']}",
                    "scope": expected["current"]["scope"],
                    "knowledge_state": "revised",
                    "confidence": 0.9,
                }
            ),
            "historical": json.dumps(
                {
                    "value": f"Provisionally, {expected['historical']['value']}",
                    "scope": expected["historical"]["scope"],
                    "knowledge_state": "initial",
                    "confidence": 0.8,
                }
            ),
            "repair": json.dumps(
                {
                    "invalidated": [expected["repair"]["invalidated"]],
                    "preserved": [expected["repair"]["preserved"]],
                    "confidence": 0.95,
                }
            ),
        },
        "capabilities": {},
    }
    paraphrased = evaluate_outcome_v2(paraphrased_trial, bitemporal)
    cases.append(
        _case(
            "bitemporal-hedged-paraphrase-and-equivalent-granularity",
            bitemporal.public.family,
            "accept",
            paraphrased["metrics"]["task_success"] == 1.0,
            paraphrased["metrics"],
        )
    )
    ambiguous_trial = copy.deepcopy(paraphrased_trial)
    ambiguous = json.loads(ambiguous_trial["answers"]["repair"])
    ambiguous["invalidated"].append("an unrelated decision")
    ambiguous_trial["answers"]["repair"] = json.dumps(ambiguous)
    ambiguous_evaluation = evaluate_outcome_v2(ambiguous_trial, bitemporal)
    cases.append(
        _case(
            "bitemporal-overbroad-granularity",
            bitemporal.public.family,
            "reject",
            ambiguous_evaluation["metrics"]["repair_accuracy"] == 1.0,
            ambiguous_evaluation["metrics"],
        )
    )

    recursive = generate_recursive_investigation(42, variants=1)[0]
    recursive_gold = RecursiveInvestigationOracleExecutor().run(recursive)
    recursive_evaluation = evaluate_recursive_v2(recursive_gold, recursive)
    cases.append(
        _case(
            "recursive-gold",
            recursive.public.family,
            "accept",
            recursive_evaluation["metrics"]["task_success"] == 1.0,
            recursive_evaluation["metrics"],
        )
    )
    incident = IncidentWorld.from_dict(recursive.hidden_world["incident_world"])
    corrected_incident = IncidentWorld.from_dict(
        recursive.hidden_world["corrected_incident_world"]
    )
    remediation = _paraphrase_remediation(incident.correct_remediation)
    recursive_answer = {
        "root_service": incident.root_service,
        "root_cause": f"Based on available evidence, likely {incident.root_cause}",
        "remediation": remediation,
        "confidence": 0.9,
    }
    recursive_trial = {
        "answers": {
            "derive": json.dumps(recursive_answer),
            "reuse": json.dumps(
                {
                    **recursive_answer,
                    "basis": "previously derived conclusion",
                }
            ),
            "repair": json.dumps(
                {
                    "root_service": corrected_incident.root_service,
                    "root_cause": (
                        f"Based on available evidence, likely "
                        f"{corrected_incident.root_cause}"
                    ),
                    "remediation": _paraphrase_remediation(
                        corrected_incident.correct_remediation
                    ),
                    "superseded_conclusion": incident.root_cause,
                    "confidence": 0.9,
                }
            ),
            "reuse_repaired": json.dumps(
                {
                    "root_service": corrected_incident.root_service,
                    "root_cause": corrected_incident.root_cause,
                    "remediation": _paraphrase_remediation(
                        corrected_incident.correct_remediation
                    ),
                    "basis": "revised conclusion",
                    "confidence": 0.9,
                }
            ),
        },
        "retrievals": {
            "reuse": {
                "context": (
                    f"{incident.root_service} {incident.root_cause} "
                    f"{incident.correct_remediation}"
                ),
                "context_tokens": 20,
            },
            "reuse_repaired": {
                "context": (
                    f"superseded_conclusion={incident.root_cause}; "
                    f"{corrected_incident.root_service} "
                    f"{corrected_incident.root_cause} "
                    f"{corrected_incident.correct_remediation}"
                ),
                "context_tokens": 24,
            },
        },
        "capabilities": {},
    }
    recursive_paraphrase = evaluate_outcome_v2(recursive_trial, recursive)
    cases.append(
        _case(
            "recursive-hedged-answer-and-equivalent-action",
            recursive.public.family,
            "accept",
            recursive_paraphrase["metrics"]["task_success"] == 1.0,
            recursive_paraphrase["metrics"],
        )
    )
    stale_repair_trial = copy.deepcopy(recursive_trial)
    stale_repair_trial["answers"]["reuse_repaired"] = stale_repair_trial["answers"]["reuse"]
    stale_repair = evaluate_outcome_v2(stale_repair_trial, recursive)
    cases.append(
        _case(
            "recursive-stale-conclusion-after-premise-invalidation",
            recursive.public.family,
            "reject",
            stale_repair["metrics"]["trace_verified_repaired_reuse_accuracy"] == 1.0,
            stale_repair["metrics"],
        )
    )
    unsupported_trial = copy.deepcopy(recursive_trial)
    unsupported_trial["retrievals"]["reuse"] = {"context": "", "context_tokens": 0}
    unsupported = evaluate_outcome_v2(unsupported_trial, recursive)
    cases.append(
        _case(
            "recursive-correct-answer-without-retrieval-support",
            recursive.public.family,
            "reject",
            unsupported["metrics"]["trace_verified_reuse_accuracy"] == 1.0,
            unsupported["metrics"],
        )
    )

    decision = generate_decision_lineage(42, variants=1)[0]
    decision_gold = DecisionLineageOracleExecutor().run(decision)
    decision_evaluation = evaluate_decision_lineage_v2(decision_gold, decision)
    cases.append(
        _case(
            "decision-lineage-gold",
            decision.public.family,
            "accept",
            decision_evaluation["metrics"]["task_success"] == 1.0,
            decision_evaluation["metrics"],
        )
    )
    decision_incident = IncidentWorld.from_dict(decision.hidden_world["incident_world"])
    decision_remediation = _paraphrase_remediation(decision_incident.correct_remediation)
    decision_answer = {
        "evidence": f"According to available evidence, {decision_incident.root_signal}",
        "constraint": "reduce customer disruption",
        "decision": (
            f"Use {decision_remediation} on {decision_incident.root_service}"
        ),
        "action": f"Used {decision_remediation} on {decision_incident.root_service}",
        "outcome": "The incident was fixed and the service is healthy",
        "later_evidence_excluded": True,
        "confidence": 0.9,
    }
    decision_trial = {
        "answers": {"audit": json.dumps(decision_answer)},
        "capabilities": {},
    }
    decision_paraphrase = evaluate_outcome_v2(decision_trial, decision)
    cases.append(
        _case(
            "decision-lineage-paraphrase-and-alternative-valid-action",
            decision.public.family,
            "accept",
            decision_paraphrase["metrics"]["task_success"] == 1.0,
            decision_paraphrase["metrics"],
        )
    )
    contaminated_trial = copy.deepcopy(decision_trial)
    contaminated_answer = dict(decision_answer)
    contaminated_answer["evidence"] += (
        f"; later forensics identified {decision_incident.root_cause}"
    )
    contaminated_trial["answers"]["audit"] = json.dumps(contaminated_answer)
    contaminated = evaluate_outcome_v2(contaminated_trial, decision)
    cases.append(
        _case(
            "decision-lineage-post-hoc-evidence",
            decision.public.family,
            "reject",
            contaminated["metrics"]["audit_faithfulness"] == 1.0,
            contaminated["metrics"],
        )
    )

    failures = [row for row in cases if not row["passed"]]
    return {
        "schema_version": 1,
        "case_count": len(cases),
        "families": sorted({row["family"] for row in cases}),
        "passed": not failures,
        "failures": failures,
        "cases": cases,
        "boundary": (
            "mechanical adversarial validation only; independent human agreement remains required"
        ),
    }
