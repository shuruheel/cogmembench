from __future__ import annotations

from argparse import Namespace

from cogmembench import cli
from cogmembench.evaluators.equivalence import equivalent_value
from cogmembench.validation.evaluator_adversarial import (
    validate_evaluator_adversarial_corpus,
)


def test_evaluator_adversarial_corpus_accepts_and_rejects_matched_cases() -> None:
    result = validate_evaluator_adversarial_corpus()

    assert result["passed"]
    assert result["case_count"] == 11
    assert {row["expected"] for row in result["cases"]} == {"accept", "reject"}
    assert set(result["families"]) == {
        "bitemporal_belief_revision",
        "recursive_investigation",
        "decision_lineage",
    }


def test_equivalence_policy_allows_bounded_hedging_but_rejects_conflicts() -> None:
    assert equivalent_value("According to available evidence, likely March 21", "March 21")
    assert equivalent_value("revised", "corrected")
    assert equivalent_value(["March 21"], "March 21")
    assert not equivalent_value("March 12 or March 21", "March 21")
    assert not equivalent_value(["March 21", "March 12"], "March 21")
    assert not equivalent_value("not March 21", "March 21")


def test_evaluator_adversarial_validation_is_available_from_cli(tmp_path) -> None:
    output = tmp_path / "evaluators.json"

    exit_code = cli.cmd_validate_evaluators_v2(Namespace(output=str(output)))

    assert exit_code == 0
    assert output.exists()
