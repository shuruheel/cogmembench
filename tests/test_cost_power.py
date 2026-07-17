from __future__ import annotations

import pytest

from cogmembench.reports import build_power_analysis, build_run_cost_model
from cogmembench.reports.power import required_paired_worlds


def trial(world: str, condition: str, score: float, *, backend: str = "reference") -> dict:
    return {
        "scenario_id": world,
        "family": "recursive_investigation",
        "difficulty_tier": "hard",
        "condition": condition,
        "model": "model-a",
        "repetition": 1,
        "backend": backend,
        "valid": True,
        "metrics": {
            "input_tokens": 100,
            "output_tokens": 20,
            "lifecycle_tokens": 140,
            "read_context_tokens": 20,
            "memory_construction_tokens": 20,
            "model_calls": 2,
            "memory_tool_calls": 1,
            "memory_storage_growth": 2,
            "latency_ms": 50,
            "estimated_inference_cost_usd": 0.01,
            "estimated_embedding_cost_usd": 0.001,
        },
        "evaluation": {"metrics": {"task_success": score}},
    }


def test_cost_model_projects_complete_local_matrix() -> None:
    rows = [trial("w1", "stateless", 0.0), trial("w1", "automatic-passive", 1.0)]
    result = build_run_cost_model(
        rows,
        {
            "budget_usd": 1,
            "worlds": 10,
            "models": 1,
            "repetitions": 1,
            "conditions": ["stateless", "automatic-passive"],
        },
    )
    assert result["projection"]["cost_complete"] is True
    assert result["projection"]["known_cost_lower_bound_usd"] == pytest.approx(0.22)
    assert result["projection"]["budget_status"] == "within_budget"


def test_cost_model_never_silently_zeroes_unpriced_external_cost() -> None:
    rows = [trial("w1", "automatic-passive", 1.0, backend="mem0-oss")]
    result = build_run_cost_model(
        rows,
        {
            "budget_usd": 100,
            "worlds": 10,
            "models": 1,
            "repetitions": 1,
            "conditions": ["automatic-passive"],
        },
    )
    assert result["projection"]["cost_complete"] is False
    assert result["projection"]["budget_status"] == "indeterminate_lower_bound"
    assert any("substrate_server" in value for value in result["projection"]["unknown_components"])


def test_power_analysis_is_paired_by_world_and_provisional_without_freeze() -> None:
    rows = []
    for index in range(12):
        baseline = 0.2 if index % 2 else 0.0
        rows.extend(
            (
                trial(f"w{index}", "stateless", baseline),
                trial(f"w{index}", "automatic-passive", baseline + 0.4),
            )
        )
    result = build_power_analysis(
        rows,
        metric="task_success",
        treatment="automatic-passive",
        baseline="stateless",
        minimum_effect=0.2,
        assumed_sd=0.3,
        comparisons=3,
    )
    assert result["tiers"]["hard"]["pilot_pairs"] == 12
    assert result["tiers"]["hard"]["required_worlds"] > 2
    assert result["publication_ready"] is False


def test_power_formula_rejects_invalid_inputs_and_handles_zero_variance() -> None:
    assert required_paired_worlds(minimum_effect=0.2, paired_sd=0.0) == 2
    with pytest.raises(ValueError):
        required_paired_worlds(minimum_effect=0.0, paired_sd=1.0)
