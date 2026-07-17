from __future__ import annotations

from cogmembench.agents import (
    COGNITIVE_TOOLS,
    CognitiveOperationContext,
    CognitiveOperationDispatcher,
)
from cogmembench.substrate import ReferenceSubstrateAdapter


def context(logical_time: int) -> CognitiveOperationContext:
    return CognitiveOperationContext("tool-world", logical_time, "agent", "s1", logical_time)


def test_cognitive_tool_contract_has_no_private_reasoning_operation():
    names = {tool["function"]["name"] for tool in COGNITIVE_TOOLS}

    assert names == {
        "substrate_record",
        "substrate_revise",
        "substrate_link",
        "substrate_retrieve",
        "substrate_audit",
    }
    assert not any("chain" in name or "thought" in name for name in names)


def test_dispatcher_records_revises_links_and_retrieves_with_logical_time():
    adapter = ReferenceSubstrateAdapter()
    adapter.reset("tool-world")
    dispatcher = CognitiveOperationDispatcher(adapter)
    evidence = dispatcher.execute(
        "substrate_record",
        {
            "artifact_id": "evidence",
            "kind": "evidence",
            "content": "authoritative alpha bulletin",
            "valid_start": 5,
            "status": "accepted",
            "provenance_event_ids": ["event-1"],
        },
        context(10),
    )
    claim = dispatcher.execute(
        "substrate_record",
        {
            "artifact_id": "claim-old",
            "kind": "claim",
            "content": "alpha limit 100",
            "valid_start": 5,
            "status": "accepted",
        },
        context(10),
    )
    dispatcher.execute(
        "substrate_link",
        {
            "source_id": evidence["artifact_id"],
            "relation": "supports",
            "target_id": claim["artifact_id"],
            "strength": 1.0,
        },
        context(10),
    )
    revised = dispatcher.execute(
        "substrate_revise",
        {
            "artifact_id": "claim-old",
            "revision_id": "claim-new",
            "kind": "claim",
            "content": "alpha limit 240",
            "valid_start": 5,
            "status": "accepted",
            "provenance_event_ids": ["event-2"],
        },
        context(20),
    )
    historical = dispatcher.execute(
        "substrate_retrieve",
        {
            "query": "alpha limit",
            "max_items": 5,
            "valid_at": 5,
            "known_at": 15,
        },
        context(21),
    )

    assert revised["revision_of"] == "claim-old"
    assert {row["artifact_id"] for row in historical["results"]} == {
        "evidence",
        "claim-old",
    }


def test_dispatcher_audit_uses_only_observed_decision_time_retrievals():
    adapter = ReferenceSubstrateAdapter()
    adapter.reset("tool-world")
    dispatcher = CognitiveOperationDispatcher(adapter)
    dispatcher.execute(
        "substrate_record",
        {
            "artifact_id": "decision",
            "kind": "decision",
            "content": "choose alpha",
            "valid_start": 1,
            "status": "accepted",
        },
        context(1),
    )

    receipt = dispatcher.execute("substrate_audit", {"decision_ref": "decision"}, context(1))

    assert receipt["decision_ref"] == "decision"
    assert receipt["retrieved_artifact_ids"] == ()
