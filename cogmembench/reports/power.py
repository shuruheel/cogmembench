from __future__ import annotations

import math
import statistics
from collections import defaultdict
from statistics import NormalDist
from typing import Any


def paired_world_differences(
    rows: list[dict[str, Any]],
    *,
    metric: str,
    treatment: str,
    baseline: str,
    tier_field: str = "difficulty_tier",
) -> dict[str, list[float]]:
    cells: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    for row in rows:
        if not row.get("valid", True) or not row.get("scenario_id"):
            continue
        value = row.get("evaluation", {}).get("metrics", {}).get(metric)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        key = (
            str(row.get(tier_field, "unspecified")),
            str(row["scenario_id"]),
            str(row.get("model", "unspecified")),
            str(row.get("repetition", "unspecified")),
        )
        cells[(str(row.get("condition")), *key)].append(float(value))
    treatment_keys = {key[1:] for key in cells if key[0] == treatment}
    baseline_keys = {key[1:] for key in cells if key[0] == baseline}
    result: dict[str, list[float]] = defaultdict(list)
    for tier, world, model, repetition in sorted(treatment_keys & baseline_keys):
        treatment_values = cells[(treatment, tier, world, model, repetition)]
        baseline_values = cells[(baseline, tier, world, model, repetition)]
        result[tier].append(
            statistics.mean(treatment_values) - statistics.mean(baseline_values)
        )
    return dict(result)


def required_paired_worlds(
    *,
    minimum_effect: float,
    paired_sd: float,
    alpha: float = 0.05,
    power: float = 0.8,
    comparisons: int = 1,
) -> int:
    """Normal-approximation sample size for a two-sided paired contrast."""
    if minimum_effect <= 0 or paired_sd < 0:
        raise ValueError("minimum_effect must be positive and paired_sd non-negative")
    if not 0 < alpha < 1 or not 0 < power < 1 or comparisons <= 0:
        raise ValueError("invalid alpha, power, or comparisons")
    if paired_sd == 0:
        return 2
    adjusted_alpha = alpha / comparisons
    z_alpha = NormalDist().inv_cdf(1 - adjusted_alpha / 2)
    z_power = NormalDist().inv_cdf(power)
    return max(2, math.ceil(((z_alpha + z_power) * paired_sd / minimum_effect) ** 2))


def build_power_analysis(
    rows: list[dict[str, Any]],
    *,
    metric: str,
    treatment: str,
    baseline: str,
    minimum_effect: float,
    alpha: float = 0.05,
    target_power: float = 0.8,
    comparisons: int = 1,
    tier_field: str = "difficulty_tier",
    assumed_sd: float | None = None,
    frozen_pilot: bool = False,
    minimum_pilot_pairs: int = 12,
) -> dict[str, Any]:
    differences = paired_world_differences(
        rows,
        metric=metric,
        treatment=treatment,
        baseline=baseline,
        tier_field=tier_field,
    )
    tiers = sorted(differences) or ["all"]
    estimates: dict[str, Any] = {}
    ready = frozen_pilot
    for tier in tiers:
        values = differences.get(tier, [])
        observed_sd = statistics.stdev(values) if len(values) > 1 else None
        sd = assumed_sd if assumed_sd is not None else observed_sd
        if len(values) < minimum_pilot_pairs:
            ready = False
        if sd is None:
            estimates[tier] = {
                "pilot_pairs": len(values),
                "observed_mean_difference": statistics.mean(values) if values else None,
                "observed_paired_sd": observed_sd,
                "planning_sd": None,
                "required_worlds": None,
                "status": "insufficient_variance_estimate",
            }
            ready = False
            continue
        estimates[tier] = {
            "pilot_pairs": len(values),
            "observed_mean_difference": statistics.mean(values) if values else None,
            "observed_paired_sd": observed_sd,
            "planning_sd": sd,
            "required_worlds": required_paired_worlds(
                minimum_effect=minimum_effect,
                paired_sd=sd,
                alpha=alpha,
                power=target_power,
                comparisons=comparisons,
            ),
            "status": (
                "frozen_pilot_estimate"
                if frozen_pilot and len(values) >= minimum_pilot_pairs
                else "provisional"
            ),
        }
    return {
        "schema_version": 1,
        "method": "two-sided paired normal approximation at the scenario/world unit",
        "metric": metric,
        "contrast": {"treatment": treatment, "baseline": baseline},
        "tier_field": tier_field,
        "minimum_effect": minimum_effect,
        "alpha_familywise": alpha,
        "target_power": target_power,
        "multiplicity": {
            "method": "Bonferroni",
            "comparisons": comparisons,
            "per_comparison_alpha": alpha / comparisons,
        },
        "minimum_pilot_pairs_per_tier": minimum_pilot_pairs,
        "frozen_pilot": frozen_pilot,
        "publication_ready": ready and all(
            estimate["required_worlds"] is not None for estimate in estimates.values()
        ),
        "tiers": estimates,
        "interpretation": (
            "Publication sample-size input from a frozen pilot."
            if ready
            else "Provisional planning output; do not freeze publication sample sizes from it."
        ),
    }
