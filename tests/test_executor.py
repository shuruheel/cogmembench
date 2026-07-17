from __future__ import annotations

import json

from cogmembench.agents import DevelopmentV2TrialExecutor, OracleTrialExecutor, TrialExecutor
from cogmembench.agents.base import format_memory_hit
from cogmembench.memory import ReferenceCognitiveMemory
from cogmembench.providers import DeterministicProvider
from cogmembench.scenarios.generators import generate_development_v2, generate_suite
from cogmembench.telemetry import EventLog


def _scenario():
    return generate_suite("smoke", 42, 1, [42], 8)[0].public


def test_task_delivery_user_events_identical_across_conditions(tmp_path):
    expected = [event.content for event in _scenario().events]
    for condition in (
        "stateless",
        "transcript",
        "flat",
        "mindgraph-passive",
        "mindgraph-active-prefetch",
        "mindgraph-active-pull",
    ):
        log = EventLog(tmp_path / f"{condition}.jsonl")
        memory = ReferenceCognitiveMemory() if condition.startswith("mindgraph") else None
        TrialExecutor(DeterministicProvider(), condition, log, memory=memory).run(_scenario())
        seen = []
        turns = set()
        for event in log.by_type("model_call"):
            key = (event.session_id, event.turn_id)
            if key in turns:
                continue
            turns.add(key)
            users = [m["content"] for m in event.payload["messages"] if m.get("role") == "user"]
            seen.append(users[-1])
        assert seen == expected


def test_active_captures_tool_and_retrieval_traces(tmp_path):
    log = EventLog(tmp_path / "trace.jsonl")
    row = TrialExecutor(DeterministicProvider(), "mindgraph-active-prefetch", log, memory=ReferenceCognitiveMemory()).run(_scenario())
    tools = log.by_type("tool_call")
    assert any(event.payload["tool"] == "mindgraph_capture" for event in tools)
    assert any(event.payload["tool"] == "mindgraph_retrieve" for event in tools)
    assert row["metrics"]["memory_tool_calls"] >= 2


def test_active_pull_counts_explicit_retrieval_context_tokens(tmp_path):
    log = EventLog(tmp_path / "pull.jsonl")
    row = TrialExecutor(
        DeterministicProvider(),
        "mindgraph-active-pull",
        log,
        memory=ReferenceCognitiveMemory(),
    ).run(_scenario())
    assert any(
        event.payload["tool"] == "mindgraph_retrieve" for event in log.by_type("tool_call")
    )
    assert row["metrics"]["retrieved_context_tokens"] > 0


def test_prompts_do_not_contain_hidden_keys(tmp_path):
    log = EventLog(tmp_path / "leak.jsonl")
    TrialExecutor(DeterministicProvider(), "transcript", log).run(_scenario())
    blob = json.dumps([event.payload["messages"] for event in log.by_type("model_call")])
    assert "hidden_world" not in blob
    assert "expected_answer" not in blob
    assert "expected_retrieval_ids" not in blob


def test_token_accounting_separates_replay_and_retrieval(tmp_path):
    transcript = TrialExecutor(DeterministicProvider(), "transcript", EventLog(tmp_path / "t.jsonl")).run(_scenario())
    passive = TrialExecutor(DeterministicProvider(), "mindgraph-passive", EventLog(tmp_path / "p.jsonl"), memory=ReferenceCognitiveMemory()).run(_scenario())
    assert transcript["metrics"]["historical_context_tokens"] > 0
    assert transcript["metrics"]["retrieved_context_tokens"] == 0
    assert passive["metrics"]["retrieved_context_tokens"] > 0


def test_memory_context_formatter_is_concise_and_preserves_status():
    hit = {
        "node_type": "Preference",
        "label": "Regional transport",
        "summary": "Use rental car",
        "confidence": 0.9,
        "superseded": True,
        "props": {"large": "payload that should not be injected"},
    }
    text = format_memory_hit(hit)
    assert text == "[Preference superseded confidence=0.90] Regional transport: Use rental car"
    assert "payload" not in text


def test_oracle_writes_only_annotated_durable_memories(tmp_path):
    scenario = generate_suite("smoke", 42, 1, [42], 8)[0]
    log = EventLog(tmp_path / "oracle.jsonl")
    row = OracleTrialExecutor(
        DeterministicProvider(),
        log,
        memory=ReferenceCognitiveMemory(),
    ).run(scenario)
    assert row["condition"] == "oracle-policy"
    assert row["metrics"]["tool_calls_by_type"]["oracle_retrieve"] == 2
    assert len(row["memory_snapshot"]["records"]) == len(scenario.evaluator.durable)
    assert not any(
        "lobby code" in record["text"].lower()
        for record in row["memory_snapshot"]["records"]
    )
    assert any(
        edge["edge_type"] == "Supersedes"
        for edge in row["memory_snapshot"]["edges"]
    )


def test_oracle_preserves_non_evidence_provenance_targets(tmp_path):
    scenario = generate_suite("smoke", 42, 1, [42], 8)[-1]
    row = OracleTrialExecutor(
        DeterministicProvider(),
        EventLog(tmp_path / "oracle-failure.jsonl"),
        memory=ReferenceCognitiveMemory(),
    ).run(scenario)
    labels = {record["label"] for record in row["memory_snapshot"]["records"]}
    assert f"{scenario.public.scenario_id}:failure" in labels
    assert len(labels) == len(scenario.evaluator.durable)
    assert any(
        edge["edge_type"] == "Supports"
        for edge in row["memory_snapshot"]["edges"]
    )


def test_development_v2_snapshots_before_terminal_session_ingestion(tmp_path):
    scenario = generate_development_v2(42)[0]
    row = DevelopmentV2TrialExecutor(
        DeterministicProvider(),
        "mindgraph-passive",
        EventLog(tmp_path / "decision-time.jsonl"),
        memory=ReferenceCognitiveMemory(),
    ).run(scenario.public)

    terminal_text = scenario.public.events[-1].content
    stored = " ".join(record["text"] for record in row["memory_snapshot"]["records"])
    assert terminal_text not in stored
    assert row["metrics"]["terminal_session_excluded_from_ingestion"]
    assert row["metrics"]["evaluation_checkpoints"] == 2
    assert set(row["answers"]) == set(scenario.evaluator.expected_answers)
