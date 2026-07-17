from __future__ import annotations

import json
from copy import deepcopy
from argparse import Namespace

import pytest

from cogmembench import cli
from cogmembench.reports import build_hierarchical_analysis


def row(
    scenario_id: str,
    family: str,
    difficulty: str,
    condition: str,
    score: float,
    *,
    ablation: str | None = None,
    depth: int | None = None,
) -> dict:
    metrics = {
        "task_success": score,
        "raw_reuse_accuracy": score,
        "trace_verified_reuse_accuracy": score,
        "conclusion_revision_accuracy": score,
        "trace_verified_repaired_reuse_accuracy": score,
        "stale_conclusion_intrusion_rate": 1.0 - score,
        "downstream_repair_accuracy": score,
    }
    return {
        "scenario_id": scenario_id,
        "family": family,
        "difficulty_tier": difficulty,
        "realization_pattern": f"{family}-{difficulty}",
        "derivation_depth": depth,
        "condition": condition,
        "ablation": ablation,
        "ablation_applied": ablation is not None,
        "valid": True,
        "evaluation": {"metrics": metrics},
    }


def analysis_rows() -> list[dict]:
    rows = []
    worlds = (
        ("r-easy", "recursive_investigation", "easy", 3, 1.0),
        ("r-medium", "recursive_investigation", "medium", 4, 0.8),
        ("r-hard", "recursive_investigation", "hard", 5, 0.6),
        ("b-easy", "bitemporal_belief_revision", "easy", None, 1.0),
        ("b-medium", "bitemporal_belief_revision", "medium", None, 0.8),
        ("b-hard", "bitemporal_belief_revision", "hard", None, 0.6),
    )
    for scenario_id, family, difficulty, depth, full_score in worlds:
        for _ in range(2):
            rows.append(row(scenario_id, family, difficulty, "stateless", 0.0, depth=depth))
            rows.append(
                row(
                    scenario_id,
                    family,
                    difficulty,
                    "automatic-passive",
                    full_score,
                    depth=depth,
                )
            )
            rows.append(
                row(
                    scenario_id,
                    family,
                    difficulty,
                    "automatic-passive",
                    full_score - 0.4,
                    ablation="no-temporal-metadata",
                    depth=depth,
                )
            )
    return rows


def test_hierarchical_analysis_uses_worlds_not_repeated_rows_as_primary_units() -> None:
    result = build_hierarchical_analysis(analysis_rows(), iterations=200, seed=7)

    full = result["conditions"]["automatic-passive"]
    assert full["n_worlds"] == 6
    assert full["n_observations"] == 12
    assert full["mean"] == pytest.approx(0.8)
    paired = result["paired_effects_vs_baseline"]["effects"]["automatic-passive"]
    assert paired["n_worlds"] == 6
    assert paired["mean"] == pytest.approx(0.8)


def test_hierarchical_analysis_reports_ablation_depth_repair_and_variance() -> None:
    result = build_hierarchical_analysis(analysis_rows(), iterations=200, seed=11)

    ablation = result["ablation_effects"][
        "automatic-passive|no-temporal-metadata"
    ]["effect"]
    assert ablation["n_worlds"] == 6
    assert ablation["mean"] == pytest.approx(-0.4)
    assert set(result["curves"]["recursive_by_depth"]) == {"3", "4", "5"}
    assert set(result["curves"]["recursive_revision_by_depth"]) == {"3", "4", "5"}
    assert set(result["curves"]["revision_by_difficulty"]) == {
        "easy",
        "medium",
        "hard",
    }
    variance = result["variance_components"]["automatic-passive"]
    assert variance["n_families"] == 2
    assert variance["n_templates"] == 6
    assert variance["n_worlds"] == 6


def test_hierarchical_analysis_reports_treatment_by_model_interaction() -> None:
    model_a = analysis_rows()
    for item in model_a:
        item["model"] = "model-a"
    model_b = deepcopy(model_a)
    for item in model_b:
        item["model"] = "model-b"
        if item["condition"] == "automatic-passive" and not item["ablation_applied"]:
            item["evaluation"]["metrics"]["task_success"] += 0.1

    result = build_hierarchical_analysis(model_a + model_b, iterations=100, seed=17)
    interaction = result["treatment_by_model_interactions"][
        "automatic-passive|model-b-vs-model-a"
    ]["effect"]

    assert interaction["n_worlds"] == 6
    assert interaction["mean"] == pytest.approx(0.1)


def test_hierarchical_bootstrap_is_deterministic_and_available_from_cli(tmp_path) -> None:
    rows = analysis_rows()
    first = build_hierarchical_analysis(rows, iterations=100, seed=19)
    second = build_hierarchical_analysis(rows, iterations=100, seed=19)
    assert first == second

    evaluated = tmp_path / "evaluated.jsonl"
    output = tmp_path / "analysis.json"
    evaluated.write_text("".join(json.dumps(item) + "\n" for item in rows))
    exit_code = cli.cmd_analyze_cognitive_v2(
        Namespace(
            evaluated=str(evaluated),
            metric="task_success",
            baseline_cell="stateless",
            bootstrap_iterations=100,
            bootstrap_seed=19,
            output=str(output),
        )
    )

    assert exit_code == 0
    assert json.loads(output.read_text())["statistical_unit"] == "scenario/world"


def test_hierarchical_analysis_rejects_nonidentical_public_worlds() -> None:
    rows = analysis_rows()[:2]
    rows[0]["scenario_public_hash"] = "first"
    rows[1]["scenario_public_hash"] = "second"

    with pytest.raises(ValueError, match="public hashes differ"):
        build_hierarchical_analysis(rows, iterations=100)
