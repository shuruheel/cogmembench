from __future__ import annotations

import json

from cogmembench.environments import IncidentWorld
from cogmembench.scenarios.derivation import DerivationDAG, ReDerivabilityControl
from cogmembench.scenarios.generators import generate_recursive_investigation
from cogmembench.scenarios.schema import model_view


def test_recursive_generator_is_deterministic_and_uses_executable_incident_worlds():
    first = generate_recursive_investigation(42)
    second = generate_recursive_investigation(42)

    assert [row.to_dict() for row in first] == [row.to_dict() for row in second]
    assert len(first) == 5
    for scenario in first:
        world = IncidentWorld.from_dict(scenario.hidden_world["incident_world"])
        assert world.world_id in scenario.public.events[0].content
        assert world.root_cause not in scenario.public.events[0].content


def test_recursive_dag_depth_breadth_and_rederivability_controls_are_mechanical():
    scenario = generate_recursive_investigation(7, variants=1)[0]
    dag = DerivationDAG.from_dict(scenario.hidden_world["derivation_dag"])
    control = ReDerivabilityControl.from_dict(scenario.hidden_world["rederivability_control"])
    decision_id = f"{scenario.public.scenario_id}:reuse-decision"

    assert dag.depth(decision_id) == scenario.hidden_world["derivation_depth"] == 3
    assert dag.breadth() == scenario.hidden_world["derivation_breadth"] == 3
    assert control.budget_asymmetry >= 2.0
    assert control.derived_artifact_tokens <= control.read_budget_tokens
    assert control.premise_session_count >= 4


def test_recursive_public_view_excludes_ground_truth_and_marks_reuse_checkpoint():
    scenario = generate_recursive_investigation(9, variants=1)[0]
    public = json.dumps(model_view(scenario.public))

    assert "derivation_dag" not in public
    assert "required_reuse_artifact_id" not in public
    assert scenario.public.events[-1].checkpoint_id == "reuse_repaired"
    assert scenario.public.events[-1].phase == "reuse"


def test_recursive_difficulty_tiers_raise_derivation_depth_and_evidence_burden():
    scenarios = generate_recursive_investigation(42, variants=3)

    assert [row.hidden_world["difficulty_tier"] for row in scenarios] == [
        "easy",
        "medium",
        "hard",
    ]
    assert [row.hidden_world["derivation_depth"] for row in scenarios] == [3, 4, 5]
    assert [
        row.hidden_world["rederivability_control"]["premise_session_count"]
        for row in scenarios
    ] == [6, 7, 8]


def test_recursive_worlds_invalidate_a_required_premise_and_mint_a_distinct_repair():
    for scenario in generate_recursive_investigation(42, variants=3):
        hidden = scenario.hidden_world
        dag = DerivationDAG.from_dict(hidden["derivation_dag"])
        control = hidden["failure_amplification_control"]
        initial = IncidentWorld.from_dict(hidden["incident_world"])
        corrected = IncidentWorld.from_dict(hidden["corrected_incident_world"])
        by_id = {node.artifact_id: node for node in dag.nodes}

        def ancestors(artifact_id: str) -> set[str]:
            inputs = set(by_id[artifact_id].input_ids)
            return inputs | {ancestor for item in inputs for ancestor in ancestors(item)}

        assert control["invalidated_premise_id"] in ancestors(
            control["stale_conclusion_id"]
        )
        assert initial.root_service != corrected.root_service
        assert initial.root_cause != corrected.root_cause
        assert set(scenario.evaluator.expected_answers) == {
            "derive",
            "reuse",
            "repair",
            "reuse_repaired",
        }
