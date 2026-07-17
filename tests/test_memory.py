from __future__ import annotations

from cogmembench.memory import (
    FlatHybridMemoryStore,
    FlatMemoryStore,
    MindGraphHTTPMemory,
    ReferenceCognitiveMemory,
)
from cogmembench.memory.reset import contamination_test


def test_flat_bm25_prefers_matching_record():
    store = FlatMemoryStore()
    store.add("prefers trains and avoids red eyes", "s1")
    store.add("unrelated weather note", "s1")
    hits = store.search("train preference red eyes", 1)
    assert hits and "trains" in hits[0]["text"]


def test_flat_hybrid_records_both_retrieval_legs():
    class Embeddings:
        def embed(self, texts):
            return [
                [1.0, 0.0] if "train" in text.lower() else [0.0, 1.0]
                for text in texts
            ]

        def telemetry(self):
            return {"embedding_calls": 3}

    store = FlatHybridMemoryStore(Embeddings())
    store.add_many(["prefers trains", "weather note"], "s1")
    hits = store.search("trains travel", 1)
    assert hits[0]["text"] == "prefers trains"
    assert {leg["mode"] for leg in hits[0]["legs"]} == {"text", "semantic"}


def test_reference_reset_has_no_stale_retrieval():
    result = contamination_test(ReferenceCognitiveMemory())
    assert result["passed"]
    assert "SENTINEL_ALPHA" not in str(result["stale_hits"])


def test_supersession_is_observable():
    store = ReferenceCognitiveMemory()
    first = store.write("preference", "prefer train", "s1")
    second = store.write("preference", "Correction: prefer bus; supersedes train", "s2")
    snapshot = store.snapshot()
    assert first.superseded_by == second.uid
    assert any(edge["edge_type"] == "Supersedes" for edge in snapshot["edges"])


def test_http_snapshot_captures_edges():
    memory = MindGraphHTTPMemory("http://example.test", backend_label="mindgraph-local")
    calls = []

    def request(method, path, body=None):
        calls.append((method, path, body))
        if path == "/stats":
            return {"total_nodes": 2, "total_edges": 1}
        if path.startswith("/nodes"):
            return {"items": [{"uid": "a"}, {"uid": "b"}]}
        return [{"uid": "e", "from_uid": "a", "to_uid": "b", "edge_type": "Supports"}]

    memory._request = request  # type: ignore[method-assign]
    snapshot = memory.snapshot()
    assert snapshot["edges"][0]["edge_type"] == "Supports"
    assert ("POST", "/edges/batch", {"uids": ["a", "b"]}) in calls


def test_http_provider_telemetry_aggregates_without_inventing_embedding_tokens():
    memory = MindGraphHTTPMemory("http://example.test", backend_label="mindgraph-local")
    memory._ingestion_telemetry = [
        {
            "extraction": {
                "requests": 3,
                "responses": 2,
                "failed_requests": 1,
                "usage_reported_responses": 2,
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
            },
            "embedding": {
                "requests": 1,
                "responses": 1,
                "failed_requests": 0,
                "submitted_input_items": 4,
                "submitted_input_chars": 800,
                "output_vectors": 4,
            },
        }
    ]
    telemetry = memory.provider_telemetry()
    assert telemetry["metrics"]["mindgraph_extraction_total_tokens"] == 120
    assert telemetry["metrics"]["mindgraph_embedding_input_items"] == 4
    assert telemetry["extraction_token_usage_complete"]
    assert not telemetry["embedding_token_usage_available"]
    assert "mindgraph_embedding_input_tokens" not in telemetry["metrics"]
