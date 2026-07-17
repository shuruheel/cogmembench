from __future__ import annotations

from pathlib import Path

from cogmembench.agents import CognitiveAgentTrialExecutor
from cogmembench.evaluators import evaluate_outcome_v2
from cogmembench.providers import DeterministicProvider
from cogmembench.scenarios.generators import generate_bitemporal_belief_revision
from cogmembench.substrate import ReferenceSubstrateAdapter
from cogmembench.substrate.conditions import COGNITIVE_V2_CONDITIONS
from cogmembench.telemetry import EventLog


def test_automatic_passive_uses_bitemporal_retrieval_axes(tmp_path: Path) -> None:
    scenario = generate_bitemporal_belief_revision(42, variants=1)[0]
    trial = CognitiveAgentTrialExecutor(
        DeterministicProvider(),
        COGNITIVE_V2_CONDITIONS["automatic-passive"],
        EventLog(tmp_path / "trace.jsonl"),
        adapter=ReferenceSubstrateAdapter(),
    ).run(scenario)

    assert trial["retrievals"]["current"]["artifact_ids"]
    assert trial["retrievals"]["historical"]["artifact_ids"]
    evaluation = evaluate_outcome_v2(trial, scenario)
    assert evaluation["metrics"]["current_belief_accuracy"] == 1
    assert evaluation["metrics"]["historical_belief_accuracy"] >= 2 / 3
    assert trial["usage"]["read_operations"] >= 3


def test_agent_directed_condition_routes_standard_tools(tmp_path: Path) -> None:
    scenario = generate_bitemporal_belief_revision(42, variants=1)[0]
    trial = CognitiveAgentTrialExecutor(
        DeterministicProvider(),
        COGNITIVE_V2_CONDITIONS["agent-directed-active"],
        EventLog(tmp_path / "trace.jsonl"),
        adapter=ReferenceSubstrateAdapter(),
    ).run(scenario)

    assert trial["metrics"]["tool_calls_by_type"]["substrate_record"] >= 3
    assert trial["metrics"]["tool_calls_by_type"]["substrate_retrieve"] == 3
    assert trial["retrievals"]["current"]["artifact_ids"]


def test_matched_and_full_transcript_conditions_have_distinct_context_budgets(
    tmp_path: Path,
) -> None:
    scenario = generate_bitemporal_belief_revision(42, variants=1)[0]
    event = scenario.public.events[-1]
    prior = [
        {"role": "user", "content": "one two three four five six"},
        {"role": "assistant", "content": "seven eight nine ten eleven twelve"},
    ]
    matched = CognitiveAgentTrialExecutor(
        DeterministicProvider(),
        COGNITIVE_V2_CONDITIONS["transcript"],
        EventLog(tmp_path / "matched.jsonl"),
        retrieval_tokens=5,
    )
    full = CognitiveAgentTrialExecutor(
        DeterministicProvider(),
        COGNITIVE_V2_CONDITIONS["transcript-full"],
        EventLog(tmp_path / "full.jsonl"),
        retrieval_tokens=5,
    )

    matched_messages = matched._messages(scenario, event, prior, "")
    full_messages = full._messages(scenario, event, prior, "")

    assert matched_messages == [matched_messages[0], matched_messages[-1]]
    assert full_messages[1:3] == prior
