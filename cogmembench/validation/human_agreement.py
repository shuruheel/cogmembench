from __future__ import annotations

import hashlib
import random
import statistics
from collections import Counter, defaultdict
from typing import Any

from ..scenarios.world import LedgerOperation, WorldLedger
from ..scenarios.schema import Scenario

RELATION_LABELS = [
    "supports",
    "contradicts",
    "derived_from",
    "depends_on",
    "supersedes",
    "motivates",
    "implements",
    "produces",
    "learned_from",
    "applies_to",
    "invalidates",
    "unrelated",
    "ambiguous",
]

DECISION_RULES = {
    "supports": "The subject is evidence or a reason that raises support for the object.",
    "contradicts": "The subject and object make mutually incompatible claims in the same scope.",
    "derived_from": "The subject is an inference computed from the object.",
    "depends_on": "The subject remains valid or executable only if the object holds.",
    "supersedes": "The subject is the newer replacement for the object while preserving history.",
    "motivates": "The subject decision or goal is the reason the object action was chosen.",
    "implements": "The subject action or plan realizes the object decision or goal.",
    "produces": "The subject action causally yields the object outcome.",
    "learned_from": "The subject lesson was consolidated from the object experience or failure.",
    "applies_to": "The subject rule is valid for the object situation or scope.",
    "invalidates": "The subject correction makes the object no longer acceptable in its scope.",
    "unrelated": "No listed directed relation is supported between subject and object.",
    "ambiguous": "The supplied text is insufficient to choose one relation without guessing.",
}

ANCHORS = (
    ("supports", "The database saturation metric is sustained.", "The database is overloaded."),
    ("contradicts", "The cache is unavailable.", "The cache is healthy."),
    ("derived_from", "The failure is caused by pool exhaustion.", "The pool metric and trace."),
    ("depends_on", "Deploy the repair plan.", "The rollback window remains open."),
    ("supersedes", "Use parser version 3.", "Use parser version 2."),
    ("motivates", "Choose the low-impact repair.", "Apply the low-impact repair."),
    ("implements", "Apply the low-impact repair.", "Choose the low-impact repair."),
    ("produces", "Restart the exhausted worker pool.", "Request latency recovers."),
    ("learned_from", "Check pool limits before scaling workers.", "The pool exhaustion failure."),
    ("applies_to", "Use bounded retries for transient failures.", "A transient network reset."),
    ("invalidates", "The timestamp was corrected to Tuesday.", "The event occurred Monday."),
    ("unrelated", "The database metric is elevated.", "The design review is next Thursday."),
)


def _task(subject: str, object_: str, gold: str, locator: str) -> dict[str, Any]:
    task_id = hashlib.sha256(f"{locator}\0{gold}\0{subject}\0{object_}".encode()).hexdigest()[:24]
    return {
        "task_id": task_id,
        "task_type": "relation_vocabulary",
        "subject_text": subject,
        "object_text": object_,
        "question": "Which relation best completes: SUBJECT [relation] OBJECT?",
        "labels": RELATION_LABELS,
        "gold": gold,
    }


def build_blinded_annotation_packet(
    scenarios: list[Scenario], *, sample_size: int = 50, seed: int = 1729
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates = [
        _task(subject, object_, gold, f"anchor:{index}")
        for index, (gold, subject, object_) in enumerate(ANCHORS)
    ]
    for scenario in scenarios:
        ledger_data = scenario.hidden_world.get("world_ledger")
        if not ledger_data:
            continue
        ledger = WorldLedger.from_dict(ledger_data)
        artifacts = {
            entry.artifact.artifact_id: entry.artifact
            for entry in ledger.entries
            if entry.artifact is not None
        }
        for entry in ledger.entries:
            if entry.operation is LedgerOperation.LINK and entry.relation is not None:
                subject = artifacts.get(str(entry.source_id))
                object_ = artifacts.get(str(entry.target_id))
                if subject and object_:
                    candidates.append(
                        _task(
                            subject.content,
                            object_.content,
                            entry.relation.value,
                            f"{scenario.public.scenario_id}:{entry.sequence}",
                        )
                    )
            elif entry.operation is LedgerOperation.REVISE and entry.artifact is not None:
                old = artifacts.get(str(entry.target_id))
                if old:
                    candidates.append(
                        _task(
                            entry.artifact.content,
                            old.content,
                            "supersedes",
                            f"{scenario.public.scenario_id}:{entry.sequence}:revision",
                        )
                    )
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        by_label[str(row["gold"])].append(row)
    rng = random.Random(seed)
    for rows in by_label.values():
        rng.shuffle(rows)
    selected = []
    active_labels = [label for label in RELATION_LABELS if by_label[label]]
    while len(selected) < sample_size and active_labels:
        for label in list(active_labels):
            if len(selected) >= sample_size:
                break
            if by_label[label]:
                selected.append(by_label[label].pop())
            if not by_label[label]:
                active_labels.remove(label)
    tasks = [{key: value for key, value in row.items() if key != "gold"} for row in selected]
    answer_key = {row["task_id"]: row["gold"] for row in selected}
    return (
        {
            "schema_version": 1,
            "blinding": {
                "condition_hidden": True,
                "product_identity_hidden": True,
                "scenario_ids_hidden": True,
                "gold_separate": True,
            },
            "instructions_version": "relation-v1",
            "decision_rules": DECISION_RULES,
            "tasks": tasks,
        },
        {"schema_version": 1, "answers": answer_key},
    )


def _fleiss_kappa(labels_by_task: dict[str, list[str]]) -> float | None:
    if not labels_by_task:
        return None
    counts = [Counter(labels) for labels in labels_by_task.values()]
    raters = {sum(row.values()) for row in counts}
    if len(raters) != 1 or next(iter(raters)) < 2:
        return None
    n_raters = next(iter(raters))
    categories = sorted({label for row in counts for label in row})
    observed = statistics.mean(
        sum(count * (count - 1) for count in row.values()) / (n_raters * (n_raters - 1))
        for row in counts
    )
    total = len(counts) * n_raters
    proportions = {
        category: sum(row[category] for row in counts) / total for category in categories
    }
    expected = sum(value * value for value in proportions.values())
    if expected == 1:
        return 1.0 if observed == 1 else None
    return (observed - expected) / (1 - expected)


def score_human_agreement(
    annotations: list[dict[str, str]],
    *,
    answer_key: dict[str, str] | None = None,
    kappa_threshold: float = 0.8,
    gold_accuracy_threshold: float = 0.9,
) -> dict[str, Any]:
    by_task: dict[str, dict[str, str]] = defaultdict(dict)
    for row in annotations:
        task_id = str(row["task_id"])
        annotator = str(row["annotator_id"])
        label = str(row["label"])
        if label not in RELATION_LABELS:
            raise ValueError(f"unknown relation label: {label}")
        if annotator in by_task[task_id]:
            raise ValueError(f"duplicate annotation for {task_id} by {annotator}")
        by_task[task_id][annotator] = label
    complete = {task: list(rows.values()) for task, rows in by_task.items() if len(rows) >= 2}
    kappa = _fleiss_kappa(complete)
    majority = {
        task: Counter(labels).most_common(1)[0][0] for task, labels in complete.items()
    }
    gold_pairs = [
        majority[task] == gold
        for task, gold in (answer_key or {}).items()
        if task in majority
    ]
    missing_gold_tasks = sorted(set(answer_key or {}) - set(majority))
    gold_accuracy = sum(gold_pairs) / len(gold_pairs) if gold_pairs else None
    annotators = sorted({str(row["annotator_id"]) for row in annotations})
    passed = (
        len(annotators) >= 2
        and kappa is not None
        and kappa >= kappa_threshold
        and not missing_gold_tasks
        and (gold_accuracy is None or gold_accuracy >= gold_accuracy_threshold)
    )
    return {
        "schema_version": 1,
        "annotators": annotators,
        "independent_annotator_count": len(annotators),
        "tasks_annotated": len(by_task),
        "tasks_with_two_or_more_raters": len(complete),
        "fleiss_kappa": kappa,
        "gold_majority_accuracy": gold_accuracy,
        "missing_gold_tasks": missing_gold_tasks,
        "thresholds": {
            "fleiss_kappa": kappa_threshold,
            "gold_majority_accuracy": gold_accuracy_threshold,
        },
        "passed": passed,
    }
