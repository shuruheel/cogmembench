from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from ..scenarios.schema import ExpectedAction, Scenario
from ..telemetry.tokens import count_tokens
from .deterministic import (
    _json_answer,
    _memory_match,
    _norm,
    _record_text,
    _value_match,
    evaluate_trial as evaluate_trial_v1,
)


MEMORY_METRICS = (
    "memory_precision",
    "memory_recall",
    "memory_contamination",
    "supersession_correctness",
    "provenance_completeness",
    "structural_quality",
    "retrieval_precision",
    "retrieval_recall",
)


def _event_key(event: Any) -> tuple[str, int]:
    return str(getattr(event, "session_id", "")), int(getattr(event, "turn_id", 0))


def _recursive_hits(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for child in value for item in _recursive_hits(child)]
    if not isinstance(value, dict):
        return []
    if any(key in value for key in ("node_type", "primitive", "summary", "memory_id")):
        return [value]
    hits = []
    for key, child in value.items():
        if key in {"graph", "nodes", "results", "items", "context"}:
            hits.extend(_recursive_hits(child))
    return hits


def _expected_texts(action: ExpectedAction, scenario: Scenario) -> list[str]:
    by_id = {memory.memory_id: memory.text for memory in scenario.evaluator.durable}
    return [by_id[memory_id] for memory_id in action.memory_ids if memory_id in by_id]


def _relevant_hits(hits: list[dict[str, Any]], texts: list[str]) -> list[dict[str, Any]]:
    return [
        hit
        for hit in hits
        if any(_memory_match(text, _record_text(hit)) >= 0.35 for text in texts)
    ]


def _write_primitive(event: Any) -> str:
    payload = getattr(event, "payload", {})
    tool = str(payload.get("tool", ""))
    action = str(payload.get("arguments", {}).get("action", ""))
    if tool == "mindgraph_capture":
        return "preference" if action == "journal" else action
    if tool == "mindgraph_reason":
        return "question" if action in {"question", "open_question"} else action
    if tool == "mindgraph_commit":
        return "decision" if "decision" in action or action in {"add_option", "add_constraint"} else action
    if tool == "mindgraph_plan":
        if "policy" in action:
            return "policy"
        if "execution" in action:
            return "execution"
        return "task"
    return ""


def _write_text(event: Any) -> str:
    args = getattr(event, "payload", {}).get("arguments", {})
    return " ".join(
        str(value)
        for key, value in args.items()
        if key in {"label", "summary", "content", "claim", "evidence", "props"}
    )


def _tool_policy(
    trial: dict[str, Any], scenario: Scenario, trace_events: list[Any]
) -> dict[str, float | None]:
    active = str(trial.get("condition", "")).startswith("mindgraph-active")
    if not active:
        return {
            "appropriate_retrieval_rate": None,
            "missed_retrieval_rate": None,
            "unnecessary_retrieval_rate": None,
            "appropriate_write_rate": None,
            "missed_write_rate": None,
            "harmful_write_rate": None,
            "redundant_write_rate": None,
            "correct_primitive_selection": None,
        }
    tool_events = [
        event for event in trace_events if getattr(event, "event_type", "") == "tool_call"
    ]
    retrieval_events = [
        event for event in trace_events if getattr(event, "event_type", "") == "retrieval"
    ]
    tool_by_turn: dict[tuple[str, int], list[Any]] = defaultdict(list)
    prefetch_by_turn: dict[tuple[str, int], list[Any]] = defaultdict(list)
    for event in tool_events:
        tool_by_turn[_event_key(event)].append(event)
    for event in retrieval_events:
        prefetch_by_turn[_event_key(event)].append(event)

    expected_retrieval = [
        action for action in scenario.evaluator.expected_actions if action.operation == "retrieve"
    ]
    expected_writes = [
        action for action in scenario.evaluator.expected_actions if action.operation == "write"
    ]
    retrieval_hits = 0
    unnecessary = 0
    explicit_retrievals = 0
    expected_retrieval_turns = {_event_key(action) for action in expected_retrieval}
    useful_context_tokens = 0
    for action in expected_retrieval:
        key = _event_key(action)
        texts = _expected_texts(action, scenario)
        prefetched = [
            hit
            for event in prefetch_by_turn.get(key, [])
            for hit in _recursive_hits(getattr(event, "payload", {}).get("returned", []))
        ]
        explicit_events = [
            event
            for event in tool_by_turn.get(key, [])
            if getattr(event, "payload", {}).get("tool") == "mindgraph_retrieve"
        ]
        explicit_retrievals += len(explicit_events)
        explicit_hits = [
            hit
            for event in explicit_events
            for hit in _recursive_hits(getattr(event, "payload", {}).get("observation", {}))
        ]
        useful = _relevant_hits(prefetched + explicit_hits, texts)
        retrieval_hits += bool(useful)
        useful_context_tokens += sum(count_tokens(_record_text(hit)) for hit in useful)
        if _relevant_hits(prefetched, texts):
            unnecessary += len(explicit_events)
    for event in tool_events:
        if getattr(event, "payload", {}).get("tool") != "mindgraph_retrieve":
            continue
        if _event_key(event) not in expected_retrieval_turns:
            explicit_retrievals += 1
            unnecessary += 1

    matched_writes = 0
    primitive_hits = 0
    expected_write_turns = {_event_key(action) for action in expected_writes}
    for action in expected_writes:
        candidates = [
            event
            for event in tool_by_turn.get(_event_key(action), [])
            if getattr(event, "payload", {}).get("tool") != "mindgraph_retrieve"
        ]
        primitive_candidates = [
            event for event in candidates if _write_primitive(event) == action.primitive
        ]
        primitive_hits += bool(primitive_candidates)
        texts = _expected_texts(action, scenario)
        matched_writes += any(
            any(_memory_match(text, _write_text(event)) >= 0.25 for text in texts)
            for event in primitive_candidates
        )
    all_writes = [
        event
        for event in tool_events
        if getattr(event, "payload", {}).get("tool") != "mindgraph_retrieve"
    ]
    harmful = sum(
        _event_key(event) not in expected_write_turns for event in all_writes
    )
    normalized_writes = [
        (_event_key(event), _write_primitive(event), _norm(_write_text(event)))
        for event in all_writes
    ]
    redundant = len(normalized_writes) - len(set(normalized_writes))
    return {
        "appropriate_retrieval_rate": retrieval_hits / len(expected_retrieval) if expected_retrieval else 1.0,
        "missed_retrieval_rate": 1 - retrieval_hits / len(expected_retrieval) if expected_retrieval else 0.0,
        "unnecessary_retrieval_rate": unnecessary / explicit_retrievals if explicit_retrievals else 0.0,
        "appropriate_write_rate": matched_writes / len(expected_writes) if expected_writes else 1.0,
        "missed_write_rate": 1 - matched_writes / len(expected_writes) if expected_writes else 0.0,
        "harmful_write_rate": harmful / len(all_writes) if all_writes else 0.0,
        "redundant_write_rate": redundant / len(all_writes) if all_writes else 0.0,
        "correct_primitive_selection": primitive_hits / len(expected_writes) if expected_writes else 1.0,
        "retrieved_useful_context_tokens": float(useful_context_tokens),
    }


def evaluate_trial_v2(
    trial: dict[str, Any], scenario: Scenario, trace_events: list[Any]
) -> dict[str, Any]:
    base = evaluate_trial_v1(trial, scenario, trace_events)
    expected_by_checkpoint = scenario.evaluator.expected_answers or {
        "final": scenario.evaluator.expected_answer
    }
    supplied_answers = trial.get("answers") or {"final": trial.get("answer", "")}
    checks: dict[str, dict[str, bool]] = {}
    checkpoint_scores: dict[str, float] = {}
    answer_fields: dict[str, dict[str, Any]] = {}
    for checkpoint_id, expected in expected_by_checkpoint.items():
        parsed = _json_answer(str(supplied_answers.get(checkpoint_id, "")))
        answer_fields[checkpoint_id] = parsed
        checkpoint_checks = {
            key: _value_match(parsed.get(key, ""), value) for key, value in expected.items()
        }
        checks[checkpoint_id] = checkpoint_checks
        checkpoint_scores[checkpoint_id] = (
            sum(checkpoint_checks.values()) / len(checkpoint_checks)
            if checkpoint_checks
            else 0.0
        )
    task_success = sum(checkpoint_scores.values()) / len(checkpoint_scores)
    answer_blob = _norm(json.dumps(answer_fields, sort_keys=True))
    stale_hits = sum(
        _norm(value) in answer_blob for value in scenario.evaluator.obsolete_values
    )
    stale_rate = (
        stale_hits / len(scenario.evaluator.obsolete_values)
        if scenario.evaluator.obsolete_values
        else 0.0
    )
    family = scenario.public.family
    continuity = max(0.0, task_success - stale_rate) if family == "preference_continuity" else None
    belief_update = max(0.0, task_success - stale_rate) if family == "belief_revision" else None
    contradiction = None
    if family == "belief_revision":
        relevant = [
            value
            for checkpoint in checks.values()
            for key, value in checkpoint.items()
            if key in {"old_claim_status", "unknown_scope_status"}
        ]
        contradiction = sum(relevant) / len(relevant) if relevant else 0.0
    recovery = task_success if family in {"project_continuation", "failure_learning"} else None

    metrics = dict(base["metrics"])
    metrics.update(
        {
            "task_success": task_success,
            "continuity_accuracy": continuity,
            "belief_update_accuracy": belief_update,
            "contradiction_handling": contradiction,
            "long_horizon_recovery": recovery,
            "stale_belief_rate": stale_rate,
            **_tool_policy(trial, scenario, trace_events),
        }
    )
    if trial.get("condition") in {"stateless", "transcript"}:
        for metric in MEMORY_METRICS:
            metrics[metric] = None
    task_metrics = trial.setdefault("metrics", {})
    read_tokens = float(task_metrics.get("read_context_tokens") or 0)
    lifecycle_tokens = float(task_metrics.get("lifecycle_tokens") or 0)
    source_tokens = float(task_metrics.get("memory_source_tokens") or 0)
    construction_tokens = float(task_metrics.get("memory_construction_tokens") or 0)
    matched_count = len(base.get("matched_memory_ids", []))
    metrics["task_success_per_1k_read_tokens"] = (
        task_success * 1000 / read_tokens if read_tokens else None
    )
    metrics["tokens_per_success"] = (
        lifecycle_tokens / task_success if task_success else None
    )
    metrics["context_compression_ratio"] = (
        source_tokens / read_tokens if source_tokens and read_tokens else None
    )
    metrics["extraction_tokens_per_useful_memory"] = (
        construction_tokens / matched_count
        if construction_tokens and matched_count
        else None
    )
    return {
        "answer_fields": answer_fields,
        "checks": checks,
        "checkpoint_scores": checkpoint_scores,
        "reuse_curve": [
            {"reuse_index": index, "task_success": checkpoint_scores[checkpoint_id]}
            for index, checkpoint_id in enumerate(expected_by_checkpoint, start=1)
        ],
        "metrics": metrics,
        "matched_memory_ids": base.get("matched_memory_ids", []),
        "evaluator_version": "development-v2",
    }
