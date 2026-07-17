from __future__ import annotations

import json
from argparse import Namespace

from cogmembench import cli
from cogmembench.scenarios.generators import generate_development_v2, generate_suite
from cogmembench.scenarios.schema import model_view


def test_generation_is_deterministic():
    a = generate_suite("smoke", 42, 2, [42], 8)
    b = generate_suite("smoke", 42, 2, [42], 8)
    assert [row.to_dict() for row in a] == [row.to_dict() for row in b]
    assert len(a) == 8


def test_public_model_view_excludes_hidden_state():
    scenario = generate_suite("smoke", 42, 1, [42], 8)[0]
    encoded = json.dumps(model_view(scenario.public))
    assert "hidden_world" not in encoded
    assert "expected_answer" not in encoded
    assert "durable" not in encoded


def test_development_has_ten_variants_per_family_and_three_seeds():
    rows = generate_suite("development", 42, 10, [41, 42, 43], 8)
    assert len(rows) == 120
    counts = {}
    for row in rows:
        counts[row.public.family] = counts.get(row.public.family, 0) + 1
    assert set(counts.values()) == {30}


def test_generate_can_freeze_a_single_development_generator_seed(tmp_path):
    output = tmp_path / "development-mvp.jsonl"
    args = Namespace(
        scale="development",
        seed=42,
        output=str(output),
        generator_seeds="42",
    )

    assert cli.cmd_generate(args) == 0
    rows = [line for line in output.read_text().splitlines() if line.strip()]
    assert len(rows) == 40


def test_development_v2_is_structurally_varied_and_has_two_reuse_checkpoints():
    first = generate_development_v2(42)
    second = generate_development_v2(42)
    assert [scenario.to_dict() for scenario in first] == [scenario.to_dict() for scenario in second]
    assert len(first) == 40
    for family in {scenario.public.family for scenario in first}:
        family_rows = [scenario for scenario in first if scenario.public.family == family]
        assert len(family_rows) == 10
        assert len({scenario.public.events[0].content for scenario in family_rows}) == 10
        assert {sum(event.evaluate for event in scenario.public.events) for scenario in family_rows} == {2}
