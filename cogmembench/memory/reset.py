from __future__ import annotations

import time
from typing import Any


def contamination_test(memory: Any) -> dict[str, Any]:
    memory.reset()
    if hasattr(memory, "write"):
        memory.write("observation", "COGMEMBENCH_SENTINEL_ALPHA", "reset-a")
    elif hasattr(memory, "add"):
        memory.add("COGMEMBENCH_SENTINEL_ALPHA", "reset-a")
    else:
        # Actual API: exercise the public capture tool.
        memory.execute_tool("mindgraph_capture", {"action": "observation", "label": "sentinel alpha", "summary": "COGMEMBENCH_SENTINEL_ALPHA"}, "reset-a")
    memory.reset()
    if hasattr(memory, "write"):
        memory.write("observation", "COGMEMBENCH_SENTINEL_BETA", "reset-b")
        hits = memory.retrieve("COGMEMBENCH_SENTINEL_ALPHA", 10)
    elif hasattr(memory, "add"):
        memory.add("COGMEMBENCH_SENTINEL_BETA", "reset-b")
        hits = memory.search("COGMEMBENCH_SENTINEL_ALPHA", 10)
    else:
        memory.execute_tool("mindgraph_capture", {"action": "observation", "label": "sentinel beta", "summary": "COGMEMBENCH_SENTINEL_BETA"}, "reset-b")
        hits = memory.retrieve("COGMEMBENCH_SENTINEL_ALPHA", 10)
    diagnostic: dict[str, Any] = {}
    if hasattr(memory, "retrieve_explained"):
        explained = memory.retrieve_explained("COGMEMBENCH_SENTINEL_BETA", 10)
        legs = sorted(
            {
                str(leg.get("mode") or leg.get("leg") or leg.get("kind") or "").lower()
                for hit in explained
                for leg in (hit.get("legs") or [])
            }
            - {""}
        )
        diagnostic = {
            "retrieval_legs": legs,
            "hybrid_verified": {"fts", "vec"}.issubset(legs),
            "explained_result_count": len(explained),
            "stats_before_final_reset": memory.stats(),
        }
    contaminated = any("SENTINEL_ALPHA" in str(hit) for hit in hits)
    memory.reset()
    delayed_hits: list[Any] = []
    delayed_explained: list[Any] = []
    stats_after: dict[str, Any] = {}
    if hasattr(memory, "retrieve_explained"):
        # Exercise both the context route and the in-engine hybrid route after reset.
        for _ in range(5):
            time.sleep(0.2)
            delayed_hits = memory.retrieve("COGMEMBENCH_SENTINEL_ALPHA", 10)
            delayed_explained = memory.retrieve_explained("COGMEMBENCH_SENTINEL_ALPHA", 10)
            stats_after = memory.stats()
        contaminated = contaminated or any(
            "SENTINEL_ALPHA" in str(hit) for hit in delayed_hits + delayed_explained
        )
        embedding_count = int(stats_after.get("embedding_count", 0) or 0)
        contaminated = contaminated or embedding_count != 0
        diagnostic["stats_after_final_reset"] = stats_after
        diagnostic["delayed_context_hits"] = delayed_hits
        diagnostic["delayed_hybrid_hits"] = delayed_explained
    return {"passed": not contaminated, "stale_hits": hits, "retrieval_diagnostic": diagnostic}
