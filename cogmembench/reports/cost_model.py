from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any


KNOWN_ZERO_COST_BACKENDS = {
    "none",
    "reference",
    "reference-oracle",
    "flat",
    "summary",
    "vector",
    "hybrid",
}


def _number(mapping: dict[str, Any], key: str) -> float | None:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _row_cost(row: dict[str, Any]) -> dict[str, Any]:
    metrics = row.get("metrics", {})
    inference = _number(metrics, "estimated_inference_cost_usd")
    embedding = _number(metrics, "estimated_embedding_cost_usd")
    substrate = _number(metrics, "estimated_substrate_cost_usd")
    backend = str(row.get("backend", "unknown"))
    unknown: list[str] = []
    if inference is None:
        unknown.append("tested_agent_inference")
    if embedding is None and int(metrics.get("embedding_calls", 0) or 0) > 0:
        unknown.append("harness_embedding")
    if substrate is None:
        if backend in KNOWN_ZERO_COST_BACKENDS:
            substrate = 0.0
        else:
            unknown.append("substrate_server_inference_and_embedding")
    known = sum(value for value in (inference, embedding, substrate) if value is not None)
    return {
        "known_cost_usd": known,
        "inference_cost_usd": inference,
        "embedding_cost_usd": embedding,
        "substrate_cost_usd": substrate,
        "unknown_components": unknown,
    }


def _resource_summary(rows: list[dict[str, Any]], key: str) -> dict[str, float | int | None]:
    values = [
        float(value)
        for row in rows
        if isinstance((value := row.get("metrics", {}).get(key)), (int, float))
        and not isinstance(value, bool)
    ]
    return {
        "observations": len(values),
        "mean": statistics.mean(values) if values else None,
        "total": sum(values) if values else None,
    }


def build_run_cost_model(
    rows: list[dict[str, Any]],
    profile: dict[str, Any],
    *,
    profile_name: str = "custom",
) -> dict[str, Any]:
    """Project a benchmark matrix from measured per-trial lifecycle resources.

    The projection is deliberately a lower bound whenever a provider or substrate does not
    expose one of its billable components. Unknown components never become implicit zeroes.
    """
    valid_rows = [row for row in rows if row.get("valid", True)]
    if not valid_rows:
        raise ValueError("run-cost model requires at least one valid trial")
    conditions = [str(value) for value in profile["conditions"]]
    worlds = int(profile["worlds"])
    models = int(profile["models"])
    repetitions = int(profile["repetitions"])
    ablation_features = int(profile.get("ablation_features", 0))
    ablation_worlds = int(profile.get("ablation_worlds_per_feature", 0))
    if min(worlds, models, repetitions) <= 0:
        raise ValueError("worlds, models, and repetitions must be positive")

    by_condition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in valid_rows:
        if not row.get("ablation_applied", False):
            by_condition[str(row.get("condition", "unknown"))].append(row)
    missing_conditions = [condition for condition in conditions if not by_condition[condition]]
    condition_estimates: dict[str, Any] = {}
    known_base_cost = 0.0
    unknown_components: set[str] = set()
    for condition in conditions:
        cell_rows = by_condition[condition]
        if not cell_rows:
            condition_estimates[condition] = {
                "observations": 0,
                "mean_known_cost_usd": None,
                "projected_trials": worlds * models * repetitions,
                "projected_known_cost_usd": None,
                "unknown_components": ["unobserved_condition"],
            }
            unknown_components.add(f"unobserved_condition:{condition}")
            continue
        costs = [_row_cost(row) for row in cell_rows]
        mean_known = statistics.mean(item["known_cost_usd"] for item in costs)
        trials = worlds * models * repetitions
        projected = mean_known * trials
        known_base_cost += projected
        cell_unknown = sorted(
            {component for item in costs for component in item["unknown_components"]}
        )
        unknown_components.update(f"{condition}:{value}" for value in cell_unknown)
        condition_estimates[condition] = {
            "observations": len(cell_rows),
            "mean_known_cost_usd": mean_known,
            "projected_trials": trials,
            "projected_known_cost_usd": projected,
            "unknown_components": cell_unknown,
            "resources_per_trial": {
                key: _resource_summary(cell_rows, key)["mean"]
                for key in (
                    "input_tokens",
                    "output_tokens",
                    "reasoning_tokens",
                    "read_context_tokens",
                    "memory_construction_tokens",
                    "lifecycle_tokens",
                    "model_calls",
                    "memory_tool_calls",
                    "memory_storage_growth",
                    "latency_ms",
                )
            },
        }

    ablated = [row for row in valid_rows if row.get("ablation_applied", False)]
    ablation_trials = ablation_features * ablation_worlds * models * repetitions
    known_ablation_cost: float | None = 0.0
    if ablation_trials:
        if not ablated:
            known_ablation_cost = None
            unknown_components.add("unobserved_ablation_cells")
        else:
            ablation_costs = [_row_cost(row) for row in ablated]
            known_ablation_cost = (
                statistics.mean(item["known_cost_usd"] for item in ablation_costs)
                * ablation_trials
            )
            unknown_components.update(
                f"ablation:{component}"
                for item in ablation_costs
                for component in item["unknown_components"]
            )

    projected_known = (
        known_base_cost + known_ablation_cost
        if known_ablation_cost is not None and not missing_conditions
        else None
    )
    budget = float(profile["budget_usd"])
    complete = not unknown_components and projected_known is not None
    budget_status = (
        "within_budget"
        if complete and projected_known <= budget
        else "over_budget"
        if complete
        else "indeterminate_lower_bound"
    )
    return {
        "schema_version": 1,
        "profile": profile_name,
        "statistical_unit": "scenario/world; costs measured per complete trial lifecycle",
        "matrix": {
            "worlds": worlds,
            "models": models,
            "repetitions": repetitions,
            "conditions": conditions,
            "base_trials": worlds * models * repetitions * len(conditions),
            "ablation_features": ablation_features,
            "ablation_worlds_per_feature": ablation_worlds,
            "ablation_trials": ablation_trials,
        },
        "observations": len(valid_rows),
        "condition_estimates": condition_estimates,
        "ablation_estimate": {
            "observations": len(ablated),
            "projected_trials": ablation_trials,
            "projected_known_cost_usd": known_ablation_cost,
        },
        "projection": {
            "budget_usd": budget,
            "known_cost_lower_bound_usd": projected_known,
            "unknown_components": sorted(unknown_components),
            "cost_complete": complete,
            "budget_status": budget_status,
        },
        "resource_totals_observed": {
            key: _resource_summary(valid_rows, key)
            for key in (
                "input_tokens",
                "output_tokens",
                "reasoning_tokens",
                "read_context_tokens",
                "memory_construction_tokens",
                "lifecycle_tokens",
                "model_calls",
                "memory_tool_calls",
                "memory_storage_growth",
                "latency_ms",
            )
        },
        "interpretation": (
            "Complete measured projection."
            if complete
            else "Lower bound only: budget compliance cannot be asserted until every listed "
            "component and matrix cell is priced."
        ),
    }
