from __future__ import annotations

from cogmembench.scenarios.generators import generate_bitemporal_belief_revision
from cogmembench.validation.human_agreement import (
    DECISION_RULES,
    RELATION_LABELS,
    build_blinded_annotation_packet,
    score_human_agreement,
)


def test_annotation_packet_blinds_gold_and_identity() -> None:
    packet, key = build_blinded_annotation_packet(
        generate_bitemporal_belief_revision(3, 8, 3), sample_size=2
    )
    assert packet["tasks"]
    assert all("gold" not in task and "scenario_id" not in task for task in packet["tasks"])
    assert set(key["answers"]) == {task["task_id"] for task in packet["tasks"]}


def test_annotation_packet_covers_canonical_relation_decision_rules() -> None:
    packet, key = build_blinded_annotation_packet(
        generate_bitemporal_belief_revision(3, 8, 3), sample_size=50
    )

    assert set(packet["decision_rules"]) == set(RELATION_LABELS)
    assert set(key["answers"].values()) >= set(DECISION_RULES) - {"ambiguous"}


def test_agreement_requires_independent_raters_and_thresholds() -> None:
    annotations = [
        {"task_id": task, "annotator_id": annotator, "label": "supersedes"}
        for task in ("t1", "t2", "t3")
        for annotator in ("a", "b")
    ]
    result = score_human_agreement(
        annotations,
        answer_key={"t1": "supersedes", "t2": "supersedes", "t3": "supersedes"},
    )
    assert result["fleiss_kappa"] == 1.0
    assert result["passed"]


def test_agreement_cannot_pass_with_unannotated_answer_key_tasks() -> None:
    result = score_human_agreement(
        [
            {"task_id": "t1", "annotator_id": annotator, "label": "supersedes"}
            for annotator in ("a", "b")
        ],
        answer_key={"t1": "supersedes", "t2": "supports"},
    )

    assert result["missing_gold_tasks"] == ["t2"]
    assert not result["passed"]
