from __future__ import annotations

from typing import Any


def build_calibration_analysis(rows: list[dict[str, Any]], *, bins: int = 10) -> dict[str, Any]:
    if bins <= 1:
        raise ValueError("calibration analysis requires at least two bins")
    observations = []
    for row in rows:
        if not row.get("valid", True):
            continue
        metrics = row.get("evaluation", {}).get("metrics", {})
        confidence = metrics.get("confidence_mean")
        correctness = metrics.get("task_success")
        if (
            isinstance(confidence, (int, float))
            and not isinstance(confidence, bool)
            and isinstance(correctness, (int, float))
            and not isinstance(correctness, bool)
            and 0 <= confidence <= 1
        ):
            observations.append((float(confidence), float(correctness)))
    bin_rows = []
    weighted_gap = 0.0
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        values = [
            (confidence, correctness)
            for confidence, correctness in observations
            if low <= confidence <= high and (index == bins - 1 or confidence < high)
        ]
        if not values:
            continue
        mean_confidence = sum(row[0] for row in values) / len(values)
        mean_correctness = sum(row[1] for row in values) / len(values)
        gap = abs(mean_confidence - mean_correctness)
        weighted_gap += gap * len(values)
        bin_rows.append(
            {
                "low": low,
                "high": high,
                "count": len(values),
                "mean_confidence": mean_confidence,
                "mean_correctness": mean_correctness,
                "absolute_gap": gap,
            }
        )
    return {
        "schema_version": 1,
        "observations": len(observations),
        "bins_requested": bins,
        "expected_calibration_error": (
            weighted_gap / len(observations) if observations else None
        ),
        "bins": bin_rows,
        "invalid_rows_excluded": sum(not row.get("valid", True) for row in rows),
        "missing_confidence_rows": sum(
            row.get("valid", True) for row in rows
        )
        - len(observations),
    }
