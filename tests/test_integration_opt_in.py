from __future__ import annotations

import os

import pytest

from cogmembench.memory import MindGraphHTTPMemory, MindGraphMCPMemory
from cogmembench.memory.reset import contamination_test


@pytest.mark.skipif(os.getenv("COGMEMBENCH_INTEGRATION") != "1", reason="set COGMEMBENCH_INTEGRATION=1 for live MindGraph test")
def test_live_mindgraph_reset_and_trace_capture():
    traces = []
    backend = "mindgraph-cloud" if "api.mindgraph.cloud" in os.environ["MINDGRAPH_BASE_URL"] else "mindgraph-local"
    memory = MindGraphHTTPMemory(os.environ["MINDGRAPH_BASE_URL"], api_key=os.getenv("MINDGRAPH_API_KEY"), backend_label=backend, trace=traces.append)
    result = contamination_test(memory)
    assert result["passed"]
    assert any(trace.get("kind") == "http" for trace in traces)


@pytest.mark.skipif(os.getenv("COGMEMBENCH_INTEGRATION") != "1", reason="set COGMEMBENCH_INTEGRATION=1 for live MindGraph test")
def test_live_production_mcp_contract_and_dispatch():
    backend = "mindgraph-cloud" if "api.mindgraph.cloud" in os.environ["MINDGRAPH_BASE_URL"] else "mindgraph-local"
    memory = MindGraphMCPMemory(
        os.environ["MINDGRAPH_BASE_URL"],
        api_key=os.getenv("MINDGRAPH_API_KEY"),
        backend_label=backend,
    )
    try:
        assert {tool["function"]["name"] for tool in memory.active_tools} == {
            "mindgraph_capture",
            "mindgraph_reason",
            "mindgraph_commit",
            "mindgraph_plan",
            "mindgraph_retrieve",
        }
        assert memory.mcp_server_info["version"] == "0.10.0"
    finally:
        memory.close()
