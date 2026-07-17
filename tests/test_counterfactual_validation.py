from __future__ import annotations

from argparse import Namespace

from cogmembench import cli
from cogmembench.environments import generate_incident_world
from cogmembench.scenarios.generators import (
    generate_decision_lineage,
    generate_recursive_investigation,
)
from cogmembench.scenarios.schema import save_jsonl
from cogmembench.validation import (
    validate_counterfactual_oracles,
    validate_incident_counterfactual,
)


def test_counterfactual_oracle_resolves_only_the_correct_branch_across_tiers() -> None:
    results = [validate_incident_counterfactual(generate_incident_world(42, variant)) for variant in range(3)]

    assert all(row["passed"] for row in results)
    assert {row["difficulty_tier"] for row in results} == {"easy", "medium", "hard"}
    for row in results:
        assert row["actual_score"]["execution_success"] == 1.0
        assert row["wrong_remediation_score"]["execution_success"] == 0.0
        assert row["wrong_target_score"]["execution_success"] == 0.0


def test_counterfactual_suite_validates_unique_incident_backed_worlds() -> None:
    scenarios = [
        *generate_recursive_investigation(42, variants=3),
        *generate_decision_lineage(42, variants=3),
    ]

    result = validate_counterfactual_oracles(scenarios)

    assert result["passed"]
    assert result["worlds"] == 9
    assert result["difficulty_tiers"] == {"easy": 3, "hard": 3, "medium": 3}
    assert {row["world_role"] for row in result["results"]} == {"initial", "corrected"}


def test_counterfactual_validation_is_available_from_cli(tmp_path) -> None:
    path = tmp_path / "incidents.jsonl"
    output = tmp_path / "counterfactuals.json"
    save_jsonl(path, generate_recursive_investigation(42, variants=3))

    exit_code = cli.cmd_validate_counterfactuals_v2(
        Namespace(scenarios=str(path), output=str(output))
    )

    assert exit_code == 0
    assert output.exists()
