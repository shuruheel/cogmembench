from __future__ import annotations

from cogmembench.environments import (
    ActionKind,
    IncidentAction,
    ServiceIncidentEnvironment,
    execution_score,
    generate_incident_world,
)


def test_incident_world_generation_is_seeded_and_hides_root_cause_from_public_brief():
    first = generate_incident_world(42, 0)
    second = generate_incident_world(42, 0)

    assert first == second
    brief = first.public_brief()
    assert first.root_cause not in str(brief)
    assert first.root_service in first.services


def test_incident_actions_have_consequences_and_execution_score():
    world = generate_incident_world(42, 0)
    environment = ServiceIncidentEnvironment(world)

    symptom = environment.step(IncidentAction(ActionKind.INSPECT, world.root_service))
    wrong_target = next(service for service in world.services if service != world.root_service)
    wrong = environment.step(
        IncidentAction(
            ActionKind.REMEDIATE,
            wrong_target,
            world.distractor_remediations[0],
        )
    )
    fixed = environment.step(
        IncidentAction(
            ActionKind.REMEDIATE,
            world.root_service,
            world.correct_remediation,
        )
    )
    score = execution_score(environment)

    assert "root-signal" in symptom.signals
    assert not wrong.resolved
    assert fixed.resolved
    assert score["execution_success"] == 1.0
    assert score["true_world_correctness"] == 1.0
    assert score["total_action_cost"] == 11.0
    assert score["cost_efficiency"] < 1.0


def test_replay_is_deterministic_and_snapshot_branches_are_isolated():
    world = generate_incident_world(7, 2)
    source, target = next(edge for edge in world.dependencies if edge[1] == world.root_service)
    actions = [
        IncidentAction(ActionKind.INSPECT, world.alert_service),
        IncidentAction(ActionKind.PROBE_DEPENDENCY, source, target),
    ]
    environment = ServiceIncidentEnvironment(world)
    first = environment.replay(actions)
    snapshot = environment.snapshot()
    second = environment.replay(actions)
    branch = environment.branch(snapshot)
    branch.step(
        IncidentAction(
            ActionKind.REMEDIATE,
            world.root_service,
            world.correct_remediation,
        )
    )

    assert first == second
    assert branch.resolved
    assert not environment.resolved
    assert len(branch.history) == len(environment.history) + 1


def test_dependency_probe_rejects_non_edges():
    world = generate_incident_world(9, 1)
    environment = ServiceIncidentEnvironment(world)
    source = world.services[0]

    try:
        environment.step(IncidentAction(ActionKind.PROBE_DEPENDENCY, source, source))
    except ValueError as error:
        assert "does not directly depend" in str(error)
    else:
        raise AssertionError("non-edge dependency probe should fail")
