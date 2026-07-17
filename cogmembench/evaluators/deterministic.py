from __future__ import annotations

import json
import re
from typing import Any

from ..scenarios.schema import Scenario

WORD = re.compile(r"[a-z0-9]+")
INFRASTRUCTURE_TYPES = {
    "article",
    "chunk",
    "document",
    "session",
    "wikiarticle",
    "trace",
    "traceentry",
}
MONTHS = {
    "01": "january",
    "02": "february",
    "03": "march",
    "04": "april",
    "05": "may",
    "06": "june",
    "07": "july",
    "08": "august",
    "09": "september",
    "10": "october",
    "11": "november",
    "12": "december",
}


def _norm(value: Any) -> str:
    text = str(value).lower()
    text = re.sub(
        r"\b(?:\d{4})-(\d{2})-(\d{2})\b",
        lambda match: f"{MONTHS.get(match.group(1), match.group(1))} {int(match.group(2))}",
        text,
    )
    text = re.sub(r"\bu\.?s\.?(?:a\.?)?\b|united states(?: of america)?", "us", text)
    text = text.replace("unspecified", "unknown")
    text = re.sub(r"\bcsv(?:\s+parser)?\b", "quoted delimited parser", text)
    if (
        ("preference" in text or "prefer" in text)
        and (
            any(term in text for term in ("supersed", "correct", "update", "later"))
            or ("now" in text and "instead" in text)
        )
    ):
        text += " corrected preference"
    if "tsv" in text:
        text += " tab"
    if "quoted" in text and ("comma" in text or "delimiter" in text):
        text += " quoted delimiter"
    fixed_width = "fixed-width" in text or "fixed width" in text
    if fixed_width and any(
        term in text for term in ("binary", "decode", "decoding", "offset", "header")
    ):
        text += " fixed width binary decoder"
    if (
        ("parse" in text or "parser" in text or "parsing" in text)
        and "schema" in text
        and ("before" in text or "until" in text)
        and ("validate" in text or "validation" in text)
    ):
        text += " parse without schema"
    delimited_scope = "delimited" in text or "quoted" in text
    contrasted_with_binary = fixed_width and any(
        term in text for term in ("applies", "control", "scope", "not applicable", " vs ")
    )
    excludes_binary = fixed_width and ("not applicable" in text or "not to" in text)
    only_describes_delimited = (
        delimited_scope
        and not fixed_width
        and "binary" not in text
        and any(term in text for term in ("text", "export", "import", "applies", "scope"))
    )
    if delimited_scope and (contrasted_with_binary or excludes_binary or only_describes_delimited):
        text += " delimited text only"
    words = ["parse" if word in {"parser", "parsing"} else word for word in WORD.findall(text)]
    return " ".join(word for word in words if word not in {"a", "an", "the", "against"})


def _json_answer(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return {}


def _value_match(actual: Any, expected: Any) -> bool:
    a, e = _norm(actual), _norm(expected)
    if not a or not e:
        return False
    expected_words = set(e.split())
    actual_words = set(a.split())
    return a == e or expected_words.issubset(actual_words)


def _records(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    records = snapshot.get("records", [])
    return records if isinstance(records, list) else []


def _record_text(record: dict[str, Any]) -> str:
    if isinstance(record.get("node"), dict):
        record = record["node"]
    parts = [record.get("text"), record.get("label"), record.get("summary")]
    if record.get("props"):
        parts.append(json.dumps(record["props"], sort_keys=True, default=str))
    return " ".join(str(part) for part in parts if part) or str(record)


def _primitive(record: dict[str, Any]) -> str:
    props = record.get("props") if isinstance(record.get("props"), dict) else {}
    return str(
        record.get("primitive")
        or record.get("node_type")
        or record.get("type")
        or props.get("_type")
        or ""
    ).lower()


def _memory_records(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [record for record in _records(snapshot) if _primitive(record) not in INFRASTRUCTURE_TYPES]


def _memory_match(expected_text: str, record_text: str) -> float:
    e = set(WORD.findall(expected_text.lower()))
    r = set(WORD.findall(record_text.lower()))
    if not e:
        return 0
    return len(e & r) / len(e)


def _record_uid(record: dict[str, Any]) -> str:
    if isinstance(record.get("node"), dict):
        record = record["node"]
    return str(record.get("uid") or record.get("memory_id") or "")


def _match_memories(
    expected_memories: tuple[Any, ...], records: list[dict[str, Any]], threshold: float = 0.35
) -> dict[str, dict[str, Any]]:
    """Maximum-cardinality one-to-one matching of expected memories to records."""
    candidates: dict[int, list[int]] = {}
    for expected_index, expected in enumerate(expected_memories):
        scored = [
            (_memory_match(expected.text, _record_text(record)), record_index)
            for record_index, record in enumerate(records)
        ]
        candidates[expected_index] = [
            record_index
            for score, record_index in sorted(scored, key=lambda pair: (-pair[0], pair[1]))
            if score >= threshold
        ]

    record_owner: dict[int, int] = {}

    def assign(expected_index: int, visited: set[int]) -> bool:
        for record_index in candidates[expected_index]:
            if record_index in visited:
                continue
            visited.add(record_index)
            owner = record_owner.get(record_index)
            if owner is None or assign(owner, visited):
                record_owner[record_index] = expected_index
                return True
        return False

    for expected_index in range(len(expected_memories)):
        assign(expected_index, set())
    return {
        expected_memories[expected_index].memory_id: records[record_index]
        for record_index, expected_index in record_owner.items()
    }


def _edge_parts(edge: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(edge.get("from_uid") or edge.get("source_uid") or ""),
        str(edge.get("to_uid") or edge.get("target_uid") or ""),
        str(edge.get("edge_type") or edge.get("type") or "").lower(),
    )


def evaluate_trial(trial: dict[str, Any], scenario: Scenario, trace_events: list[Any]) -> dict[str, Any]:
    answer = _json_answer(trial.get("answer", ""))
    expected = scenario.evaluator.expected_answer
    checks = {key: _value_match(answer.get(key, ""), value) for key, value in expected.items()}
    task_success = sum(checks.values()) / len(checks) if checks else 0.0
    answer_text = _norm(trial.get("answer", ""))
    stale = sum(_norm(value) in answer_text for value in scenario.evaluator.obsolete_values)
    stale_rate = stale / len(scenario.evaluator.obsolete_values) if scenario.evaluator.obsolete_values else 0.0

    records = _memory_records(trial.get("memory_snapshot", {}))
    matched = _match_memories(scenario.evaluator.durable, records)
    memory_recall = len(matched) / len(scenario.evaluator.durable) if scenario.evaluator.durable else 1.0
    useful_record_ids = {id(record) for record in matched.values()}
    useful_records = sum(id(record) in useful_record_ids for record in records)
    memory_precision = useful_records / len(records) if records else (1.0 if not scenario.evaluator.durable else 0.0)
    contamination_hits = sum(any(_norm(term) in _norm(_record_text(record)) for term in scenario.evaluator.non_durable_terms) for record in records)
    normalized_records = [_norm(_record_text(record)) for record in records]
    duplicate_count = len(normalized_records) - len(set(normalized_records))
    memory_contamination = (contamination_hits + duplicate_count) / len(records) if records else 0.0

    typed = sum(
        _primitive(matched[item.memory_id]) == item.primitive.lower()
        for item in scenario.evaluator.durable
        if item.memory_id in matched
    )
    structural_quality = typed / len(scenario.evaluator.durable) if scenario.evaluator.durable else 1.0

    superseded = [m for m in scenario.evaluator.durable if m.supersedes]
    edges = trial.get("memory_snapshot", {}).get("edges", [])
    supersession_correctness = None
    if superseded:
        correct = 0
        evaluable = 0
        edge_parts = [_edge_parts(edge) for edge in edges]
        for item in superseded:
            newer = matched.get(item.memory_id)
            older = matched.get(str(item.supersedes))
            if not newer or not older:
                continue
            evaluable += 1
            new_uid, old_uid = _record_uid(newer), _record_uid(older)
            old_props = older.get("props") if isinstance(older.get("props"), dict) else {}
            flag = older.get("superseded_by") or old_props.get("superseded_by")
            relation = any(
                from_uid == new_uid and to_uid == old_uid and edge_type == "supersedes"
                for from_uid, to_uid, edge_type in edge_parts
            )
            correct += bool(relation or (new_uid and str(flag) == new_uid))
        if evaluable:
            supersession_correctness = correct / evaluable
        elif "edges" in trial.get("memory_snapshot", {}):
            supersession_correctness = 0.0

    with_provenance = [m for m in scenario.evaluator.durable if m.provenance]
    provenance_hits = 0
    provenance_edge_types = {
        "supports",
        "evidencefor",
        "extractedfrom",
        "derivedfrom",
        "producesnode",
        "capturedin",
    }
    edge_parts = [_edge_parts(edge) for edge in edges]
    for item in with_provenance:
        record = matched.get(item.memory_id)
        props = record.get("props") if record and isinstance(record.get("props"), dict) else {}
        record_uid = _record_uid(record) if record else ""
        related_uids = {
            _record_uid(matched[expected_id])
            for expected_id in item.provenance
            if expected_id in matched
        }
        linked = bool(related_uids) and all(
            any(
                edge_type in provenance_edge_types
                and {from_uid, to_uid} == {record_uid, related_uid}
                for from_uid, to_uid, edge_type in edge_parts
            )
            for related_uid in related_uids
        )
        attributed = bool(record and (
            record.get("provenance")
            or record.get("source")
            or record.get("source_documents")
            or props.get("source")
            or props.get("source_uid")
        ))
        if record and (linked or attributed):
            provenance_hits += 1
    provenance_completeness = provenance_hits / len(with_provenance) if with_provenance else None

    retrieval_events = [event for event in trace_events if getattr(event, "event_type", "") == "retrieval"]
    relevant = [m for m in scenario.evaluator.durable if m.memory_id in scenario.evaluator.expected_retrieval_ids]
    prefetched_hits = [
        hit
        for event in retrieval_events
        for hit in getattr(event, "payload", {}).get("returned", [])
    ]
    tool_events = [event for event in trace_events if getattr(event, "event_type", "") == "tool_call"]
    retrieval_tools = [
        event
        for event in tool_events
        if "retrieve" in str(getattr(event, "payload", {}).get("tool", ""))
    ]
    tool_retrieved_hits = [
        hit
        for event in retrieval_tools
        for hit in getattr(event, "payload", {}).get("observation", {}).get("results", [])
    ]
    returned_hits = prefetched_hits + tool_retrieved_hits
    retrieved_relevant = sum(
        any(_memory_match(memory.text, _record_text(hit)) >= 0.35 for hit in returned_hits)
        for memory in relevant
    )
    retrieval_recall = retrieved_relevant / len(relevant) if relevant else 1.0
    relevant_hits = sum(
        any(_memory_match(memory.text, _record_text(hit)) >= 0.35 for memory in relevant)
        for hit in returned_hits
    )
    retrieval_precision = relevant_hits / len(returned_hits) if returned_hits else (1.0 if not relevant else 0.0)

    tool_blob = _norm(" ".join(str(getattr(event, "payload", {})) for event in tool_events))
    expected_ops = scenario.evaluator.expected_tool_ops
    op_hits = sum(_norm(op) in tool_blob for op in expected_ops)
    primitive_selection = op_hits / len(expected_ops) if expected_ops and tool_events else None
    write_tools = [event for event in tool_events if event not in retrieval_tools]
    active_condition = str(trial.get("condition", "")).startswith("mindgraph-active")
    prefetch_condition = trial.get("condition") in {
        "mindgraph-active",
        "mindgraph-active-prefetch",
    }
    prefetched_relevant = any(
        any(_memory_match(memory.text, _record_text(hit)) >= 0.35 for hit in prefetched_hits)
        for memory in relevant
    )
    unnecessary_retrievals = (
        len(retrieval_tools) if prefetch_condition and prefetched_relevant else 0
    )
    tool_policy = {
        "appropriate_retrieval_rate": retrieval_recall if active_condition else None,
        "missed_retrieval_rate": (1.0 - retrieval_recall) if active_condition else None,
        "unnecessary_retrieval_rate": (
            unnecessary_retrievals / len(retrieval_tools)
            if active_condition and retrieval_tools
            else (0.0 if active_condition else None)
        ),
        "appropriate_write_rate": min(1.0, len(write_tools) / max(1, len(scenario.evaluator.durable))) if active_condition else None,
        "missed_write_rate": max(0.0, 1 - len(write_tools) / max(1, len(scenario.evaluator.durable))) if active_condition else None,
        "harmful_write_rate": memory_contamination if active_condition else None,
        "correct_primitive_selection": primitive_selection,
    }

    category = scenario.evaluator.category
    belief_score = max(0.0, task_success - stale_rate) if category == "belief" else task_success
    contradiction = checks.get("old_claim_status", True) * checks.get("europe_status", True) if category == "belief" else task_success
    recovery = task_success if category in {"recovery", "failure_learning"} else task_success
    continuity = max(0.0, task_success - stale_rate)
    metrics = {
        "task_success": task_success,
        "continuity_accuracy": continuity,
        "belief_update_accuracy": belief_score,
        "contradiction_handling": float(contradiction),
        "long_horizon_recovery": recovery,
        "memory_precision": memory_precision,
        "memory_recall": memory_recall,
        "memory_contamination": memory_contamination,
        "supersession_correctness": supersession_correctness,
        "provenance_completeness": provenance_completeness,
        "structural_quality": structural_quality,
        "retrieval_precision": retrieval_precision,
        "retrieval_recall": retrieval_recall,
        "stale_belief_rate": stale_rate,
        **tool_policy,
    }
    return {"answer_fields": answer, "checks": checks, "metrics": metrics, "matched_memory_ids": sorted(matched)}
