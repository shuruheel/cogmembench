from __future__ import annotations

import hashlib
import random
import statistics
from collections import defaultdict
from typing import Any, Iterable


Record = tuple[str, str, str, float]


def _cell(row: dict[str, Any]) -> str:
    condition = str(row["condition"])
    ablation = row.get("ablation")
    if ablation and row.get("ablation_applied", False):
        return f"{condition}|ablation={ablation}"
    return condition


def _numeric_metric(row: dict[str, Any], metric: str) -> float | None:
    value = row.get("evaluation", {}).get("metrics", {}).get(metric)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _records(rows: Iterable[dict[str, Any]], metric: str) -> list[Record]:
    records = []
    for row in rows:
        if not row.get("valid", True):
            continue
        value = _numeric_metric(row, metric)
        if value is None or not row.get("scenario_id"):
            continue
        records.append(
            (
                str(row.get("family", "unknown")),
                str(row.get("realization_pattern", "unspecified")),
                str(row["scenario_id"]),
                value,
            )
        )
    return records


def _mean_by_world(records: list[Record]) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for _, _, world, value in records:
        grouped[world].append(value)
    return {world: statistics.mean(values) for world, values in grouped.items()}


def _nested_sample_mean(records: list[Record], rng: random.Random) -> float:
    hierarchy: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    for family, template, world, value in records:
        hierarchy[family][template][world].append(value)
    sample: list[float] = []
    for templates in hierarchy.values():
        template_names = sorted(templates)
        for template_name in rng.choices(template_names, k=len(template_names)):
            worlds = templates[template_name]
            world_names = sorted(worlds)
            for world_name in rng.choices(world_names, k=len(world_names)):
                observations = worlds[world_name]
                within_world = rng.choices(observations, k=len(observations))
                sample.append(statistics.mean(within_world))
    return statistics.mean(sample)


def _percentile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("percentile requires values")
    index = round(probability * (len(values) - 1))
    return values[max(0, min(index, len(values) - 1))]


def _summary(records: list[Record], iterations: int, seed: int) -> dict[str, Any]:
    if not records:
        return {
            "n_worlds": 0,
            "n_observations": 0,
            "mean": None,
            "stddev_between_worlds": None,
            "ci95_low": None,
            "ci95_high": None,
        }
    world_means = list(_mean_by_world(records).values())
    rng = random.Random(seed)
    bootstrap = sorted(_nested_sample_mean(records, rng) for _ in range(iterations))
    return {
        "n_worlds": len(world_means),
        "n_observations": len(records),
        "mean": statistics.mean(world_means),
        "stddev_between_worlds": (
            statistics.stdev(world_means) if len(world_means) > 1 else 0.0
        ),
        "ci95_low": _percentile(bootstrap, 0.025),
        "ci95_high": _percentile(bootstrap, 0.975),
    }


def _derived_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{seed}:{label}".encode()).hexdigest()
    return int(digest[:16], 16)


def _paired_records(
    rows: list[dict[str, Any]], metric: str, treatment: str, baseline: str
) -> list[Record]:
    by_match: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    metadata: dict[str, tuple[str, str]] = {}
    for row in rows:
        if not row.get("valid", True) or not row.get("scenario_id"):
            continue
        value = _numeric_metric(row, metric)
        if value is None:
            continue
        world = str(row["scenario_id"])
        model = str(row.get("model", "unspecified"))
        repetition = str(row.get("repetition", "unspecified"))
        by_match[(_cell(row), world, model, repetition)].append(value)
        metadata[world] = (
            str(row.get("family", "unknown")),
            str(row.get("realization_pattern", "unspecified")),
        )
    records = []
    treatment_keys = {
        (world, model, repetition)
        for cell, world, model, repetition in by_match
        if cell == treatment
    }
    baseline_keys = {
        (world, model, repetition)
        for cell, world, model, repetition in by_match
        if cell == baseline
    }
    for world, model, repetition in sorted(treatment_keys & baseline_keys):
        family, template = metadata[world]
        difference = statistics.mean(
            by_match[(treatment, world, model, repetition)]
        ) - statistics.mean(
            by_match[(baseline, world, model, repetition)]
        )
        records.append((family, template, world, difference))
    return records


def _difference_in_differences(
    rows: list[dict[str, Any]],
    metric: str,
    treatment: str,
    baseline: str,
    model: str,
    reference_model: str,
) -> list[Record]:
    model_effects = _paired_records(
        [row for row in rows if str(row.get("model", "unspecified")) == model],
        metric,
        treatment,
        baseline,
    )
    reference_effects = _paired_records(
        [
            row
            for row in rows
            if str(row.get("model", "unspecified")) == reference_model
        ],
        metric,
        treatment,
        baseline,
    )
    by_model: dict[str, list[float]] = defaultdict(list)
    by_reference: dict[str, list[float]] = defaultdict(list)
    metadata: dict[str, tuple[str, str]] = {}
    for family, template, world, value in model_effects:
        by_model[world].append(value)
        metadata[world] = (family, template)
    for family, template, world, value in reference_effects:
        by_reference[world].append(value)
        metadata.setdefault(world, (family, template))
    return [
        (
            *metadata[world],
            world,
            statistics.mean(by_model[world]) - statistics.mean(by_reference[world]),
        )
        for world in sorted(set(by_model) & set(by_reference))
    ]


def _variance_components(records: list[Record]) -> dict[str, float | int | None]:
    if not records:
        return {
            "n_families": 0,
            "n_templates": 0,
            "n_worlds": 0,
            "between_family": None,
            "between_template": None,
            "between_world": None,
        }
    family_values: dict[str, list[float]] = defaultdict(list)
    template_values: dict[tuple[str, str], list[float]] = defaultdict(list)
    world_values: dict[str, list[float]] = defaultdict(list)
    for family, template, world, value in records:
        family_values[family].append(value)
        template_values[(family, template)].append(value)
        world_values[world].append(value)

    def variance(groups: Iterable[list[float]]) -> float:
        means = [statistics.mean(values) for values in groups]
        return statistics.pvariance(means) if len(means) > 1 else 0.0

    return {
        "n_families": len(family_values),
        "n_templates": len(template_values),
        "n_worlds": len(world_values),
        "between_family": variance(family_values.values()),
        "between_template": variance(template_values.values()),
        "between_world": variance(world_values.values()),
    }


def build_hierarchical_analysis(
    rows: list[dict[str, Any]],
    *,
    metric: str = "task_success",
    baseline_cell: str = "stateless",
    iterations: int = 2000,
    seed: int = 1729,
) -> dict[str, Any]:
    """World-first nested bootstrap and paired cognitive-v2 treatment analysis."""
    if not rows:
        raise ValueError("hierarchical analysis requires evaluated rows")
    if iterations < 100:
        raise ValueError("hierarchical bootstrap requires at least 100 iterations")
    public_hashes: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if row.get("scenario_id") and row.get("scenario_public_hash"):
            public_hashes[str(row["scenario_id"])].add(str(row["scenario_public_hash"]))
    mismatched_worlds = sorted(world for world, hashes in public_hashes.items() if len(hashes) > 1)
    if mismatched_worlds:
        raise ValueError(
            "scenario public hashes differ across matched rows: " + ", ".join(mismatched_worlds)
        )
    cells = sorted({_cell(row) for row in rows})
    condition_summaries = {
        cell: _summary(
            _records((row for row in rows if _cell(row) == cell), metric),
            iterations,
            _derived_seed(seed, f"condition:{cell}:{metric}"),
        )
        for cell in cells
    }
    paired = {}
    if baseline_cell in cells:
        paired = {
            cell: _summary(
                _paired_records(rows, metric, cell, baseline_cell),
                iterations,
                _derived_seed(seed, f"paired:{cell}:{baseline_cell}:{metric}"),
            )
            for cell in cells
            if cell != baseline_cell
        }

    models = sorted({str(row.get("model", "unspecified")) for row in rows})
    model_effects: dict[str, Any] = {}
    for model in models:
        model_rows = [
            row for row in rows if str(row.get("model", "unspecified")) == model
        ]
        model_cells = sorted({_cell(row) for row in model_rows})
        model_effects[model] = {
            cell: _summary(
                _paired_records(model_rows, metric, cell, baseline_cell),
                iterations,
                _derived_seed(seed, f"model:{model}:{cell}:{baseline_cell}:{metric}"),
            )
            for cell in model_cells
            if cell != baseline_cell and baseline_cell in model_cells
        }
    model_interactions: dict[str, Any] = {}
    if len(models) > 1 and baseline_cell in cells:
        reference_model = models[0]
        for model in models[1:]:
            for cell in cells:
                if cell == baseline_cell:
                    continue
                key = f"{cell}|{model}-vs-{reference_model}"
                model_interactions[key] = {
                    "condition": cell,
                    "model": model,
                    "reference_model": reference_model,
                    "direction": (
                        "(treatment-minus-baseline)_model minus "
                        "(treatment-minus-baseline)_reference_model"
                    ),
                    "effect": _summary(
                        _difference_in_differences(
                            rows,
                            metric,
                            cell,
                            baseline_cell,
                            model,
                            reference_model,
                        ),
                        iterations,
                        _derived_seed(seed, f"model-interaction:{key}:{metric}"),
                    ),
                }

    ablation_effects: dict[str, Any] = {}
    ablation_pairs = {
        (str(row["condition"]), str(row["ablation"]), _cell(row))
        for row in rows
        if row.get("ablation") and row.get("ablation_applied", False)
    }
    for condition, feature, ablated_cell in sorted(ablation_pairs):
        key = f"{condition}|{feature}"
        ablation_effects[key] = {
            "condition": condition,
            "feature": feature,
            "direction": "ablated_minus_full",
            "effect": _summary(
                _paired_records(rows, metric, ablated_cell, condition),
                iterations,
                _derived_seed(seed, f"ablation:{key}:{metric}"),
            ),
        }

    curves: dict[str, Any] = {"task_success_by_difficulty": {}}
    difficulties = sorted(
        {str(row.get("difficulty_tier", "unspecified")) for row in rows}
    )
    for difficulty in difficulties:
        curves["task_success_by_difficulty"][difficulty] = {
            cell: _summary(
                _records(
                    (
                        row
                        for row in rows
                        if _cell(row) == cell
                        and str(row.get("difficulty_tier", "unspecified")) == difficulty
                    ),
                    metric,
                ),
                iterations,
                _derived_seed(seed, f"difficulty:{difficulty}:{cell}:{metric}"),
            )
            for cell in cells
        }

    recursive_rows = [
        row
        for row in rows
        if row.get("family") == "recursive_investigation"
        and row.get("derivation_depth") is not None
    ]
    curves["recursive_by_depth"] = {}
    curves["recursive_revision_by_depth"] = {}
    for depth in sorted({int(row["derivation_depth"]) for row in recursive_rows}):
        depth_rows = [row for row in recursive_rows if int(row["derivation_depth"]) == depth]
        curves["recursive_by_depth"][str(depth)] = {
            cell: {
                curve_metric: _summary(
                    _records(
                        (row for row in depth_rows if _cell(row) == cell),
                        curve_metric,
                    ),
                    iterations,
                    _derived_seed(seed, f"depth:{depth}:{cell}:{curve_metric}"),
                )
                for curve_metric in (
                    "raw_reuse_accuracy",
                    "trace_verified_reuse_accuracy",
                    "task_success",
                )
            }
            for cell in cells
        }
        curves["recursive_revision_by_depth"][str(depth)] = {
            cell: {
                curve_metric: _summary(
                    _records(
                        (row for row in depth_rows if _cell(row) == cell),
                        curve_metric,
                    ),
                    iterations,
                    _derived_seed(
                        seed, f"revision-depth:{depth}:{cell}:{curve_metric}"
                    ),
                )
                for curve_metric in (
                    "conclusion_revision_accuracy",
                    "trace_verified_repaired_reuse_accuracy",
                    "stale_conclusion_intrusion_rate",
                )
            }
            for cell in cells
        }

    bitemporal_rows = [
        row for row in rows if row.get("family") == "bitemporal_belief_revision"
    ]
    curves["revision_by_difficulty"] = {}
    for difficulty in sorted(
        {str(row.get("difficulty_tier", "unspecified")) for row in bitemporal_rows}
    ):
        tier_rows = [
            row
            for row in bitemporal_rows
            if str(row.get("difficulty_tier", "unspecified")) == difficulty
        ]
        curves["revision_by_difficulty"][difficulty] = {
            cell: _summary(
                _records(
                    (row for row in tier_rows if _cell(row) == cell),
                    "downstream_repair_accuracy",
                ),
                iterations,
                _derived_seed(seed, f"repair:{difficulty}:{cell}"),
            )
            for cell in cells
        }

    worlds = {str(row["scenario_id"]) for row in rows if row.get("scenario_id")}
    missingness = {}
    for cell in cells:
        cell_rows = [row for row in rows if _cell(row) == cell]
        observed_worlds = {str(row["scenario_id"]) for row in cell_rows if row.get("scenario_id")}
        valid_worlds = {
            str(row["scenario_id"])
            for row in cell_rows
            if row.get("scenario_id") and row.get("valid", True)
        }
        missingness[cell] = {
            "expected_worlds": len(worlds),
            "observed_worlds": len(observed_worlds),
            "valid_worlds": len(valid_worlds),
            "invalid_worlds": len(observed_worlds - valid_worlds),
            "missing_worlds": len(worlds - observed_worlds),
        }

    return {
        "schema_version": 1,
        "metric": metric,
        "statistical_unit": "scenario/world",
        "bootstrap": {
            "method": "family-stratified template/world/observation nested bootstrap",
            "iterations": iterations,
            "seed": seed,
        },
        "matching_audit": {
            "public_hashes_consistent": not mismatched_worlds,
            "worlds_with_public_hashes": len(public_hashes),
            "pairing_keys": ["scenario_id", "model", "repetition"],
        },
        "conditions": condition_summaries,
        "paired_effects_vs_baseline": {
            "baseline_cell": baseline_cell,
            "effects": paired,
            "direction": "treatment_minus_baseline",
        },
        "effects_by_model": model_effects,
        "treatment_by_model_interactions": model_interactions,
        "ablation_effects": dict(sorted(ablation_effects.items())),
        "curves": curves,
        "variance_components": {
            cell: _variance_components(
                _records((row for row in rows if _cell(row) == cell), metric)
            )
            for cell in cells
        },
        "missingness": missingness,
        "mixed_effects_target": {
            "fixed_effects": "treatment * depth_tier + treatment * model",
            "random_effects": "1 | family/structural_template/world",
            "status": "preregistered target; estimation deferred to frozen pilot",
        },
    }
