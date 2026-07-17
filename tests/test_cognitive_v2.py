from __future__ import annotations

import json
from argparse import Namespace

from cogmembench import cli
from cogmembench.agents import CognitiveVerticalSliceExecutor
from cogmembench.evaluators import evaluate_cognitive_v2
from cogmembench.scenarios.generators import (
    generate_bitemporal_belief_revision,
    generate_decision_lineage,
    generate_recursive_investigation,
)
from cogmembench.scenarios.schema import load_jsonl, model_view, save_jsonl
from cogmembench.scenarios.world import CognitiveWorld, LedgerOperation
from cogmembench.validation import validate_cognitive_v2_scenarios


def test_bitemporal_generator_is_deterministic_and_structurally_varied():
    first = generate_bitemporal_belief_revision(42)
    second = generate_bitemporal_belief_revision(42)

    assert [row.to_dict() for row in first] == [row.to_dict() for row in second]
    assert len(first) == 5
    assert {row.public.schema_version for row in first} == {2}
    assert len({row.public.events[0].content for row in first}) == 5
    assert {len(row.public.events) for row in first} == {6, 7, 8}
    assert {tuple(event.phase for event in row.public.events) for row in first} == {
        ("accumulate", "decide", "perturb", "repair", "time_travel", "audit"),
        (
            "accumulate",
            "accumulate",
            "decide",
            "perturb",
            "repair",
            "time_travel",
            "audit",
        ),
        (
            "accumulate",
            "accumulate",
            "accumulate",
            "decide",
            "perturb",
            "repair",
            "time_travel",
            "audit",
        ),
    }


def test_cognitive_world_round_trips_without_exposing_hidden_ledger(tmp_path):
    scenario = generate_bitemporal_belief_revision(7, variants=1)[0]
    path = tmp_path / "world.jsonl"

    save_jsonl(path, [scenario])
    loaded = load_jsonl(path)[0]
    world = CognitiveWorld.from_hidden_world(loaded.hidden_world)

    assert json.dumps(loaded.to_dict(), sort_keys=True) == json.dumps(
        scenario.to_dict(), sort_keys=True
    )
    assert world.ledger.scenario_id == scenario.public.scenario_id
    assert "world_ledger" not in json.dumps(model_view(loaded.public))
    assert "expected_artifact_id" not in json.dumps(model_view(loaded.public))


def test_world_ledger_encodes_revision_and_dependency_repair():
    scenario = generate_bitemporal_belief_revision(11, variants=1)[0]
    world = CognitiveWorld.from_hidden_world(scenario.hidden_world)

    operations = [entry.operation for entry in world.ledger.entries]
    relations = [
        entry.relation for entry in world.ledger.entries if entry.operation is LedgerOperation.LINK
    ]

    assert operations.count(LedgerOperation.REVISE) == 3
    assert any(relation and relation.value == "invalidates" for relation in relations)
    assert [entry.sequence for entry in world.ledger.entries] == list(
        range(len(world.ledger.entries))
    )


def test_reference_vertical_slice_reconstructs_both_time_axes_and_repairs_dependencies():
    scenario = generate_bitemporal_belief_revision(42, variants=1)[0]

    trial = CognitiveVerticalSliceExecutor().run(scenario)
    evaluation = evaluate_cognitive_v2(trial, scenario)

    assert evaluation["metrics"] == {
        "belief_valid_time_accuracy": 1.0,
        "belief_known_at_accuracy": 1.0,
        "belief_v_k_accuracy": 1.0,
        "dependency_invalidation_precision": 1.0,
        "dependency_invalidation_recall": 1.0,
        "dependency_invalidation_f1": 1.0,
        "unaffected_artifact_preservation_rate": 1.0,
        "stale_conclusion_intrusion_rate": 0.0,
        "supersession_correctness": 1.0,
        "snapshot_isolation": 1.0,
        "downstream_repair_accuracy": 1.0,
        "task_success": 1.0,
    }
    results = {row["probe_id"]: row for row in trial["temporal_probe_results"]}
    assert results["current"]["selected_value"] == scenario.evaluator.expected_answers[
        "current"
    ]["value"]
    assert results["historical"]["selected_value"] == scenario.evaluator.expected_answers[
        "historical"
    ]["value"]
    assert len(trial["phase_trace"]) == len(scenario.public.events)
    assert trial["capabilities"].clock_mode.value == "native"


def test_evaluator_rejects_current_knowledge_leaking_into_historical_probe():
    scenario = generate_bitemporal_belief_revision(42, variants=1)[0]
    trial = CognitiveVerticalSliceExecutor().run(scenario)
    current = trial["temporal_probe_results"][0]
    trial["temporal_probe_results"][1] = {
        **trial["temporal_probe_results"][1],
        "selected_artifact_id": current["selected_artifact_id"],
        "selected_value": current["selected_value"],
    }

    evaluation = evaluate_cognitive_v2(trial, scenario)

    assert evaluation["metrics"]["belief_known_at_accuracy"] == 0.5
    assert evaluation["metrics"]["belief_v_k_accuracy"] == 0.5
    assert evaluation["metrics"]["task_success"] < 1.0


def test_evaluator_scores_invalidation_precision_not_only_recall():
    scenario = generate_bitemporal_belief_revision(42, variants=1)[0]
    trial = CognitiveVerticalSliceExecutor().run(scenario)
    repair = trial["repair_probe_result"]
    trial["repair_probe_result"] = {
        **repair,
        "invalidated_artifact_ids": repair["invalidated_artifact_ids"] + ["unrelated"],
    }

    evaluation = evaluate_cognitive_v2(trial, scenario)

    assert evaluation["metrics"]["dependency_invalidation_recall"] == 1.0
    assert evaluation["metrics"]["dependency_invalidation_precision"] == 0.5


def test_cli_generates_cognitive_v2_worlds(tmp_path):
    output = tmp_path / "cognitive-v2.jsonl"
    args = Namespace(
        scale="development",
        seed=42,
        output=str(output),
        generator_seeds=None,
        generator_version="cognitive-v2",
        v2_variants=2,
        family="bitemporal_belief_revision",
    )

    assert cli.cmd_generate(args) == 0
    rows = load_jsonl(output)
    assert len(rows) == 2
    assert {row.public.family for row in rows} == {"bitemporal_belief_revision"}


def test_cli_can_generate_all_implemented_cognitive_v2_families(tmp_path):
    output = tmp_path / "cognitive-core.jsonl"

    assert (
        cli.cmd_generate(
            Namespace(
                scale="development",
                seed=42,
                output=str(output),
                generator_seeds=None,
                generator_version="cognitive-v2",
                v2_variants=1,
                family="all",
            )
        )
        == 0
    )
    assert {row.public.family for row in load_jsonl(output)} == {
        "bitemporal_belief_revision",
        "decision_lineage",
        "recursive_investigation",
    }


def test_cli_cognitive_profiles_can_generate_beyond_the_five_world_ceiling(tmp_path):
    output = tmp_path / "cognitive-lite.jsonl"

    assert cli.cmd_generate(
        Namespace(
            scale="lite",
            seed=42,
            output=str(output),
            generator_seeds=None,
            generator_version="cognitive-v2",
            v2_variants=None,
            family="all",
        )
    ) == 0
    rows = load_jsonl(output)
    assert len(rows) == 60
    assert all(
        len({row.public_hash() for row in rows if row.public.family == family}) == 20
        for family in {row.public.family for row in rows}
    )


def test_gold_validation_requires_a_perfect_mechanical_ceiling(tmp_path):
    scenarios = generate_bitemporal_belief_revision(42, variants=2)
    path = tmp_path / "worlds.jsonl"
    output = tmp_path / "validation.json"
    save_jsonl(path, scenarios)

    result = validate_cognitive_v2_scenarios(scenarios)
    exit_code = cli.cmd_validate_cognitive_v2(Namespace(scenarios=str(path), output=str(output)))

    assert result["passed"]
    assert result["scenarios"] == 2
    assert exit_code == 0
    assert json.loads(output.read_text())["passed"]


def test_gold_validation_covers_recursive_investigation():
    scenarios = generate_recursive_investigation(42, variants=1)

    result = validate_cognitive_v2_scenarios(scenarios)

    assert result["passed"]
    assert result["families"] == ["recursive_investigation"]


def test_gold_validation_covers_decision_lineage():
    scenarios = generate_decision_lineage(42, variants=1)

    result = validate_cognitive_v2_scenarios(scenarios)

    assert result["passed"]
    assert result["families"] == ["decision_lineage"]


def test_adapter_contract_is_available_from_cli():
    assert cli.cmd_validate_adapter_v2(Namespace(adapter="reference")) == 0
    assert cli.cmd_validate_adapter_v2(Namespace(adapter="flat")) == 0
    assert cli.cmd_validate_adapter_v2(Namespace(adapter="summary")) == 0
    assert cli.cmd_validate_adapter_v2(Namespace(adapter="vector")) == 0
    assert cli.cmd_validate_adapter_v2(Namespace(adapter="hybrid")) == 0
