from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from cogmembench.agents.cognitive_tools import (
    CognitiveOperationContext,
    CognitiveOperationDispatcher,
)
from cogmembench.runners import CognitiveV2Runner
from cogmembench.scenarios.generators import generate_bitemporal_belief_revision
from cogmembench.scenarios.schema import save_jsonl
from cogmembench.substrate import (
    ArtifactKind,
    CognitiveArtifact,
    DeterministicHashEmbeddingProvider,
    EpistemicStatus,
    FlatSubstrateAdapter,
    HybridSubstrateAdapter,
    RetrievalBudget,
    RetrievalRepresentation,
    SummarySubstrateAdapter,
    TimeInterval,
    VectorSubstrateAdapter,
)
from cogmembench.validation import audit_adapter_portability


def artifact(artifact_id: str, content: str) -> CognitiveArtifact:
    return CognitiveArtifact(
        artifact_id=artifact_id,
        kind=ArtifactKind.CLAIM,
        content=content,
        scenario_id="baseline-world",
        valid_time=TimeInterval(0),
        epistemic_status=EpistemicStatus.ACCEPTED,
    )


class SemanticFixtureProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.items = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += bool(texts)
        self.items += len(texts)
        vectors = []
        for text in texts:
            lowered = text.lower()
            if any(term in lowered for term in ("car", "automobile", "vehicle")):
                vectors.append([1.0, 0.0, 0.0])
            elif any(term in lowered for term in ("fruit", "banana")):
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors

    def telemetry(self) -> dict[str, Any]:
        return {
            "embedding_provider": "semantic-fixture",
            "embedding_model": "fixture-v1",
            "embedding_calls": self.calls,
            "embedding_input_items": self.items,
            "embedding_input_tokens": self.items * 3,
        }


def test_flat_baseline_uses_okapi_bm25_and_exposes_rank_metadata() -> None:
    adapter = FlatSubstrateAdapter()
    adapter.reset("baseline-world")
    adapter.commit(artifact("dense", "alpha alpha alpha compact"), 1)
    adapter.commit(artifact("sparse", "alpha with many unrelated filler words here"), 2)

    result = adapter.retrieve("alpha", RetrievalBudget(2), 3)

    assert [item.artifact.artifact_id for item in result.items] == ["dense", "sparse"]
    assert result.items[0].metadata["mode"] == "bm25"
    assert result.items[0].metadata["rank"] == 1
    assert (
        adapter.capability_manifest().retrieval_representation
        is RetrievalRepresentation.CANONICAL
    )
    tool_result = CognitiveOperationDispatcher(adapter).execute(
        "substrate_retrieve",
        {"query": "alpha", "max_items": 1},
        CognitiveOperationContext("baseline-world", 4, "agent", "s1", 1),
    )
    assert "artifact_id: dense" in tool_result["results"][0]["content"]
    assert tool_result["results"][0]["retrieval_metadata"]["mode"] == "bm25"


def test_vector_baseline_can_rank_semantic_match_without_lexical_overlap() -> None:
    adapter = VectorSubstrateAdapter(SemanticFixtureProvider())
    adapter.reset("baseline-world")
    adapter.commit(artifact("semantic", "automobile registration deadline"), 1)
    adapter.commit(artifact("distractor", "banana ripening schedule"), 2)

    result = adapter.retrieve("car", RetrievalBudget(1), 3)

    assert result.items[0].artifact.artifact_id == "semantic"
    assert result.items[0].metadata == {
        "mode": "vector",
        "rank": 1,
        "cosine_score": 1.0,
    }
    usage = adapter.usage_report()
    assert usage.embedding_calls == 3
    assert usage.metadata["embedding"]["embedding_model"] == "fixture-v1"


def test_hybrid_baseline_records_bm25_and_vector_fusion_legs() -> None:
    adapter = HybridSubstrateAdapter(SemanticFixtureProvider())
    adapter.reset("baseline-world")
    adapter.commit(artifact("lexical", "car maintenance manual"), 1)
    adapter.commit(artifact("semantic", "automobile registration deadline"), 2)
    adapter.commit(artifact("distractor", "banana ripening schedule"), 3)

    result = adapter.retrieve("car", RetrievalBudget(3), 4)

    by_id = {item.artifact.artifact_id: item for item in result.items}
    assert set(by_id["lexical"].metadata["legs"]) == {"bm25", "vector"}
    assert set(by_id["semantic"].metadata["legs"]) == {"vector"}
    assert by_id["lexical"].metadata["rrf_k"] == 60
    assert by_id["lexical"].score > by_id["semantic"].score


def test_summary_baseline_emits_one_bounded_current_summary() -> None:
    adapter = SummarySubstrateAdapter(summary_tokens=30)
    adapter.reset("baseline-world")
    old = adapter.commit(artifact("old", "The launch date is March 12"), 1)
    adapter.revise(
        old.artifact_id,
        replace(artifact("new", "The corrected launch date is March 21"), revision_of="old"),
        2,
    )
    adapter.commit(artifact("other", "The venue remains Harbor Hall"), 3)

    result = adapter.retrieve("launch", RetrievalBudget(8, max_context_tokens=30), 4)

    assert len(result.items) == 1
    summary = result.items[0]
    assert summary.metadata["mode"] == "rolling-extractive-summary"
    assert summary.metadata["summary_tokens"] <= 30
    assert "March 21" in summary.artifact.content
    assert "March 12" not in summary.artifact.content
    assert adapter.capability_manifest().max_context_items == 1


@pytest.mark.parametrize(
    "adapter",
    [
        FlatSubstrateAdapter(),
        SummarySubstrateAdapter(),
        VectorSubstrateAdapter(DeterministicHashEmbeddingProvider()),
        HybridSubstrateAdapter(DeterministicHashEmbeddingProvider()),
    ],
)
def test_all_local_baselines_pass_declared_versus_observed_audit(adapter) -> None:
    result = audit_adapter_portability(adapter)

    assert result["passed"]
    assert result["coverage"]["automatic_capture"] == "present_correct"
    assert result["coverage"]["relations"] == "present_correct"


@pytest.mark.parametrize("adapter_name", ["flat", "summary", "vector", "hybrid"])
def test_runner_executes_each_local_baseline_with_mandatory_preflight(
    tmp_path: Path,
    adapter_name: str,
) -> None:
    scenario_path = tmp_path / f"{adapter_name}.jsonl"
    save_jsonl(scenario_path, generate_bitemporal_belief_revision(42, variants=1))
    runner = CognitiveV2Runner(
        conditions=["automatic-passive"],
        adapter=adapter_name,
        run_id=f"baseline-{adapter_name}",
        results_root=tmp_path / "results",
    )

    manifest = runner.run(scenario_path)

    assert manifest["completed_trials"] == 1
    assert manifest["invalid_trials"] == 0
    assert manifest["portability_audit"]["passed"]
    assert manifest["condition_backends"] == {"automatic-passive": adapter_name}
