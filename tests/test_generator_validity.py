from __future__ import annotations

from dataclasses import replace
from argparse import Namespace

from cogmembench import cli

from cogmembench.scenarios.generators import (
    generate_bitemporal_belief_revision,
    generate_decision_lineage,
    generate_recursive_investigation,
)
from cogmembench.validation.generator_validity import (
    structural_fingerprint,
    validate_generator_validity,
    validate_scenario_leakage,
)
from cogmembench.scenarios.schema import save_jsonl


def core_suite(seed: int = 42):
    return [
        *generate_bitemporal_belief_revision(seed),
        *generate_recursive_investigation(seed),
        *generate_decision_lineage(seed),
    ]


def test_core_generators_pass_structural_world_and_leakage_thresholds() -> None:
    result = validate_generator_validity(core_suite())

    assert result["passed"]
    assert result["scenario_count"] == 15
    assert result["leakage"]["passed"]
    for family in result["families"].values():
        assert family["unique_structural_templates"] >= 2
        assert family["unique_causal_worlds"] == 5
        assert family["unique_causal_world_ratio"] == 1.0
        assert family["largest_template_share"] <= 0.8
        assert set(family["difficulty_tier_counts"]) == {"easy", "medium", "hard"}


def test_calibration_scale_has_unique_seeded_worlds_and_balanced_difficulty() -> None:
    scenarios = [
        *generate_bitemporal_belief_revision(42, variants=40),
        *generate_recursive_investigation(42, variants=40),
        *generate_decision_lineage(42, variants=40),
    ]

    result = validate_generator_validity(
        scenarios,
        min_scenarios_per_family=40,
        min_worlds_per_family=40,
        max_template_share=0.5,
    )

    assert result["passed"]
    assert result["scenario_count"] == 120
    for family in result["families"].values():
        assert family["unique_causal_world_ratio"] == 1.0
        assert sorted(family["difficulty_tier_counts"].values()) == [13, 13, 14]


def test_structural_fingerprint_is_seed_invariant_but_pattern_sensitive() -> None:
    first = generate_recursive_investigation(42)
    second = generate_recursive_investigation(43)

    assert structural_fingerprint(first[0]) == structural_fingerprint(second[0])
    assert structural_fingerprint(first[0]) != structural_fingerprint(first[1])


def test_duplicate_inflation_fails_generator_validity() -> None:
    scenario = generate_bitemporal_belief_revision(42, variants=1)[0]

    result = validate_generator_validity(
        [scenario] * 5,
        require_all_core_families=False,
    )

    assert not result["passed"]
    failed = result["failures"][0]["failed_checks"]
    assert "unique_public_scenarios" in failed
    assert "structural_templates" in failed


def test_seeded_worlds_across_seeds_preserve_full_causal_diversity() -> None:
    scenarios = [
        *core_suite(42),
        *core_suite(43),
        *core_suite(44),
    ]

    result = validate_generator_validity(
        scenarios,
        min_scenarios_per_family=15,
        min_worlds_per_family=5,
    )

    assert result["passed"]
    assert all(
        family["unique_causal_worlds"] == family["scenario_count"]
        for family in result["families"].values()
    )


def test_leakage_validator_rejects_internal_id_in_public_stream() -> None:
    scenario = generate_bitemporal_belief_revision(42, variants=1)[0]
    internal_id = scenario.evaluator.durable[0].memory_id
    event = replace(
        scenario.public.events[0],
        content=scenario.public.events[0].content + f" Internal answer ID: {internal_id}",
    )
    contaminated = replace(
        scenario,
        public=replace(
            scenario.public,
            events=(event, *scenario.public.events[1:]),
        ),
    )

    result = validate_scenario_leakage(contaminated)

    assert not result["passed"]
    assert internal_id in result["leaked_internal_ids"]


def test_leakage_validator_rejects_direct_answer_in_checkpoint_prompt() -> None:
    scenario = generate_bitemporal_belief_revision(42, variants=1)[0]
    current = next(
        event for event in scenario.public.events if event.checkpoint_id == "current"
    )
    answer = scenario.evaluator.expected_answers["current"]["value"]
    leaked = replace(current, content=current.content + f" Hint: the answer is {answer}.")
    events = tuple(leaked if event is current else event for event in scenario.public.events)
    contaminated = replace(scenario, public=replace(scenario.public, events=events))

    result = validate_scenario_leakage(contaminated)

    assert not result["passed"]
    assert result["direct_checkpoint_answers"][0]["field"] == "value"


def test_generator_validity_is_available_from_cli(tmp_path) -> None:
    scenarios = tmp_path / "core.jsonl"
    output = tmp_path / "validity.json"
    save_jsonl(scenarios, core_suite())

    exit_code = cli.cmd_validate_generators_v2(
        Namespace(
            scenarios=str(scenarios),
            output=str(output),
            min_scenarios_per_family=5,
            min_templates_per_family=2,
            min_worlds_per_family=5,
            min_unique_world_ratio=0.8,
            max_template_share=0.8,
        )
    )

    assert exit_code == 0
    assert output.exists()
