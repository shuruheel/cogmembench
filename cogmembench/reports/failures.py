from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def _metric(row: dict[str, Any], key: str) -> float | None:
    value = row.get("evaluation", {}).get("metrics", {}).get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def classify_failure(row: dict[str, Any]) -> dict[str, Any]:
    error = str(row.get("error") or "").lower()
    if not row.get("valid", True):
        primary = "timeout" if "timeout" in error or "timed out" in error else "infrastructure"
        return {"primary": primary, "flags": [primary], "error": row.get("error")}
    success = _metric(row, "task_success")
    flags = []
    checks = (
        (
            "capture",
            ("write_appropriateness_f1", "appropriate_write_rate", "memory_recall"),
        ),
        (
            "retrieval",
            (
                "retrieval_appropriateness_f1",
                "appropriate_retrieval_rate",
                "retrieval_recall",
            ),
        ),
        ("retrieval_contamination", ("retrieval_precision",)),
        ("temporal_revision", ("belief_v_k_accuracy", "downstream_repair_accuracy")),
        (
            "dependency_repair",
            ("dependency_invalidation_f1", "conclusion_revision_accuracy"),
        ),
        (
            "verified_reuse",
            ("trace_verified_reuse_accuracy", "trace_verified_repaired_reuse_accuracy"),
        ),
        ("audit", ("audit_receipt_fidelity", "provenance_completeness")),
    )
    for category, metrics in checks:
        values = [_metric(row, metric) for metric in metrics]
        available = [value for value in values if value is not None]
        if available and min(available) < 1.0:
            flags.append(category)
    stale = _metric(row, "stale_conclusion_intrusion_rate")
    contamination = _metric(row, "memory_contamination")
    if (stale is not None and stale > 0) or (contamination is not None and contamination > 0):
        flags.append("stale_or_contaminated_memory")
    if success is not None and success < 1.0 and not flags:
        flags.append("execution_or_answer")
    if success == 1.0 and not flags:
        return {"primary": "success", "flags": [], "error": None}
    return {
        "primary": flags[0] if flags else "unscored",
        "flags": flags,
        "error": None,
    }


def build_failure_analysis(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("failure analysis requires rows")
    primary = Counter()
    flags = Counter()
    cells: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    classified = []
    for row in rows:
        result = classify_failure(row)
        primary[result["primary"]] += 1
        flags.update(result["flags"])
        cell = (str(row.get("family", "unknown")), str(row.get("condition", "unknown")))
        cells[cell][result["primary"]] += 1
        classified.append(
            {
                "trial_id": row.get("trial_id"),
                "scenario_id": row.get("scenario_id"),
                "family": cell[0],
                "condition": cell[1],
                **result,
            }
        )
    return {
        "schema_version": 1,
        "taxonomy": {
            "primary_is_mutually_exclusive": True,
            "flags_are_multi_label": True,
            "ordering": [
                "timeout",
                "infrastructure",
                "capture",
                "retrieval",
                "retrieval_contamination",
                "temporal_revision",
                "dependency_repair",
                "verified_reuse",
                "audit",
                "stale_or_contaminated_memory",
                "execution_or_answer",
                "unscored",
                "success",
            ],
        },
        "trials": len(rows),
        "primary_counts": dict(sorted(primary.items())),
        "flag_counts": dict(sorted(flags.items())),
        "by_family_condition": {
            f"{family}|{condition}": dict(sorted(counts.items()))
            for (family, condition), counts in sorted(cells.items())
        },
        "classified_trials": classified,
    }
