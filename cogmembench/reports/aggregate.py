from __future__ import annotations

import hashlib
import math
import random
import statistics
from collections import defaultdict
from typing import Any


def _summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "stddev": None, "ci95_low": None, "ci95_high": None}
    seed = int(hashlib.sha256(repr(values).encode()).hexdigest()[:16], 16)
    rng = random.Random(seed)
    boot = []
    for _ in range(2000):
        boot.append(sum(rng.choices(values, k=len(values))) / len(values))
    boot.sort()
    return {
        "n": len(values),
        "mean": sum(values) / len(values),
        "median": statistics.median(values),
        "stddev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "ci95_low": boot[int(0.025 * (len(boot) - 1))],
        "ci95_high": boot[int(0.975 * (len(boot) - 1))],
    }


def _stratified_summary(values: list[tuple[str, float]]) -> dict[str, float | int | None]:
    if not values:
        return _summary([])
    groups: dict[str, list[float]] = defaultdict(list)
    for family, value in values:
        groups[family].append(value)
    raw = [value for _, value in values]
    result = _summary(raw)
    seed = int(hashlib.sha256(repr(values).encode()).hexdigest()[:16], 16)
    rng = random.Random(seed)
    boot = []
    for _ in range(2000):
        sample = [
            value
            for group in groups.values()
            for value in rng.choices(group, k=len(group))
        ]
        boot.append(sum(sample) / len(sample))
    boot.sort()
    result["ci95_low"] = boot[int(0.025 * (len(boot) - 1))]
    result["ci95_high"] = boot[int(0.975 * (len(boot) - 1))]
    return result


def aggregate_results(rows: list[dict[str, Any]], composite_weights: dict[str, float]) -> dict[str, Any]:
    by_condition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_condition[row["condition"]].append(row)
    metrics = sorted({key for row in rows for key, value in row.get("evaluation", {}).get("metrics", {}).items() if isinstance(value, (int, float)) and value is not None})
    efficiency = sorted(
        {key for row in rows for key, value in row.get("metrics", {}).items() if isinstance(value, (int, float)) and not isinstance(value, bool)}
        | ({"wall_seconds"} if any(isinstance(row.get("wall_seconds"), (int, float)) for row in rows) else set())
    )
    conditions: dict[str, Any] = {}
    for condition, condition_rows in sorted(by_condition.items()):
        metric_summary = {metric: _summary([float(row["evaluation"]["metrics"][metric]) for row in condition_rows if row["evaluation"]["metrics"].get(metric) is not None]) for metric in metrics}
        eff_summary = {
            metric: _summary(
                [
                    float(row.get("wall_seconds"))
                    if metric == "wall_seconds"
                    else float(row["metrics"][metric])
                    for row in condition_rows
                    if (
                        row.get("wall_seconds")
                        if metric == "wall_seconds"
                        else row["metrics"].get(metric)
                    )
                    is not None
                ]
            )
            for metric in efficiency
        }
        composites = []
        for row in condition_rows:
            m = row["evaluation"]["metrics"]
            score = 0.0
            included_weight = 0.0
            for key, weight in composite_weights.items():
                raw_value = (
                    m.get("memory_contamination")
                    if key == "inverse_memory_contamination"
                    else m.get(key)
                )
                if raw_value is None:
                    continue
                value = 1 - raw_value if key == "inverse_memory_contamination" else raw_value
                score += weight * float(value or 0)
                included_weight += weight
            composites.append(score / included_weight if included_weight else 0.0)
        conditions[condition] = {"n": len(condition_rows), "metrics": metric_summary, "efficiency": eff_summary, "composite": _summary(composites)}

    paired: dict[str, Any] = {}
    baseline = {row["scenario_id"]: row for row in by_condition.get("stateless", [])}
    for condition, condition_rows in by_condition.items():
        if condition == "stateless":
            continue
        diffs: list[tuple[str, float]] = []
        for row in condition_rows:
            other = baseline.get(row["scenario_id"])
            if other:
                diffs.append(
                    (
                        str(row.get("family", "unknown")),
                        float(row["evaluation"]["metrics"]["task_success"])
                        - float(other["evaluation"]["metrics"]["task_success"]),
                    )
                )
        effect = None
        relative = None
        if diffs:
            diff_values = [value for _, value in diffs]
            sd = statistics.stdev(diff_values) if len(diff_values) > 1 else 0
            effect = statistics.mean(diff_values) / sd if sd else (math.inf if statistics.mean(diff_values) else 0.0)
            baseline_values = [
                float(baseline[row["scenario_id"]]["evaluation"]["metrics"]["task_success"])
                for row in condition_rows
                if row["scenario_id"] in baseline
            ]
            baseline_mean = statistics.mean(baseline_values) if baseline_values else 0
            relative = statistics.mean(diff_values) / baseline_mean if baseline_mean else None
        paired[condition] = {
            "task_success_delta_vs_stateless": _stratified_summary(diffs),
            "task_success_relative_vs_stateless": relative,
            "paired_standardized_effect": effect,
        }
    failures = [{"scenario_id": row["scenario_id"], "condition": row["condition"], "score": row["evaluation"]["metrics"]["task_success"], "answer": row.get("answer", ""), "checks": row["evaluation"].get("checks", {})} for row in rows if row.get("evaluation", {}).get("metrics", {}).get("task_success", 0) < 1]
    by_family: dict[str, Any] = {}
    for family in sorted({str(row.get("family", "unknown")) for row in rows}):
        family_rows = [row for row in rows if str(row.get("family", "unknown")) == family]
        by_family[family] = {
            condition: _summary(
                [
                    float(row["evaluation"]["metrics"]["task_success"])
                    for row in family_rows
                    if row["condition"] == condition
                ]
            )
            for condition in sorted({row["condition"] for row in family_rows})
        }
    reuse: dict[str, Any] = {}
    for condition, condition_rows in sorted(by_condition.items()):
        by_index: dict[int, list[float]] = defaultdict(list)
        for row in condition_rows:
            for point in row.get("evaluation", {}).get("reuse_curve", []):
                by_index[int(point["reuse_index"])].append(float(point["task_success"]))
        reuse[condition] = {
            str(index): _summary(values) for index, values in sorted(by_index.items())
        }
    return {"conditions": conditions, "paired": paired, "by_family": by_family, "reuse": reuse, "failures": failures, "metrics": metrics, "composite_weights": composite_weights}
