from __future__ import annotations

import json
from pathlib import Path

from cogmembench.runners import CognitiveV2Runner
from cogmembench.scenarios.generators import (
    generate_bitemporal_belief_revision,
    generate_decision_lineage,
    generate_recursive_investigation,
)
from cogmembench.scenarios.schema import save_jsonl


def test_runner_emits_balanced_cells_manifest_and_steering(tmp_path: Path) -> None:
    scenarios = [
        generate_bitemporal_belief_revision(42, variants=1)[0],
        generate_recursive_investigation(42, variants=1)[0],
        generate_decision_lineage(42, variants=1)[0],
    ]
    scenario_path = tmp_path / "suite.jsonl"
    save_jsonl(scenario_path, scenarios)
    runner = CognitiveV2Runner(
        run_id="test-cognitive-v2",
        results_root=tmp_path / "results",
    )

    manifest = runner.run(scenario_path)

    assert manifest["trial_count"] == 18
    assert manifest["completed_trials"] == 18
    assert manifest["invalid_trials"] == 0
    assert manifest["portability_audit"] is None
    rows = [json.loads(line) for line in runner.evaluated_path.read_text().splitlines()]
    assert manifest["budgets"]["matched_context_tokens"] == 1200
    assert manifest["operating_mode"] == "matched-budget"
    assert manifest["scaffold"]["version"] == "canonical-v1"
    assert len(manifest["scaffold"]["sha256"]) == 64
    assert manifest["budgets"]["full_transcript_tokens"] is None
    assert manifest["difficulty_tier_counts"] == {"easy": 3}
    assert len(rows) == 18
    assert {row["condition"] for row in rows} == set(manifest["conditions"])
    assert all(row["difficulty_tier"] == "easy" for row in rows)
    assert all("realization_pattern" in row for row in rows)
    oracle = [row for row in rows if row["condition"] == "oracle-passive"]
    assert all(row["evaluation"]["metrics"]["task_success"] == 1 for row in oracle)
    persistent = [
        row
        for row in rows
        if row["condition"] in {"automatic-passive", "agent-directed-active"}
    ]
    assert all(
        row["evaluation"]["metrics"]["write_appropriateness_f1"] is not None
        for row in persistent
    )
    assert all(
        0 <= row["evaluation"]["metrics"]["retrieval_appropriateness_f1"] <= 1
        for row in persistent
    )
    steering = json.loads(runner.steering_path.read_text())
    assert set(steering["families"]) == {scenario.public.family for scenario in scenarios}
    assert all(
        set(family["task_success_by_difficulty"]) == {"easy"}
        for family in steering["families"].values()
    )
    assert runner.steering_markdown_path.read_text().startswith(
        "# Cognitive-v2 Steering Report"
    )


def test_oracle_capture_uses_selected_compatible_substrate(tmp_path: Path) -> None:
    scenario = generate_bitemporal_belief_revision(42, variants=1)[0]
    scenario_path = tmp_path / "suite.jsonl"
    save_jsonl(scenario_path, [scenario])
    runner = CognitiveV2Runner(
        conditions=["oracle-passive"],
        adapter="flat",
        run_id="test-flat-oracle",
        results_root=tmp_path / "results",
    )

    manifest = runner.run(scenario_path)
    row = json.loads(runner.evaluated_path.read_text())

    assert manifest["condition_backends"] == {"oracle-passive": "flat"}
    assert row["backend"] == "flat"
    assert row["evaluation"]["metrics"]["task_success"] == 1
