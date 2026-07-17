from __future__ import annotations

import os

import pytest

from cogmembench.substrate import (
    CogneeRecordStore,
    MappedJournalSubstrateAdapter,
    Mem0OSSRecordStore,
    MindGraphRecordStore,
    ZepCloudRecordStore,
)
from cogmembench.validation import audit_adapter_portability


def _selected(name: str) -> bool:
    configured = {
        item.strip()
        for item in os.getenv("COGMEMBENCH_LIVE_ADAPTERS", "").split(",")
        if item.strip()
    }
    return name in configured


@pytest.mark.skipif(not _selected("mindgraph-v2"), reason="live MindGraph adapter not selected")
def test_live_mindgraph_v2_portability() -> None:
    adapter = MappedJournalSubstrateAdapter(
        MindGraphRecordStore(
            os.getenv("MINDGRAPH_BASE_URL", "http://127.0.0.1:18790"),
            api_key=os.getenv("MINDGRAPH_API_KEY"),
        )
    )
    assert audit_adapter_portability(adapter)["passed"]


@pytest.mark.skipif(not _selected("mem0-oss"), reason="live Mem0 adapter not selected")
def test_live_mem0_oss_portability() -> None:
    adapter = MappedJournalSubstrateAdapter(
        Mem0OSSRecordStore(
            os.getenv("MEM0_BASE_URL", "http://127.0.0.1:8000"),
            api_key=os.getenv("MEM0_API_KEY"),
        )
    )
    assert audit_adapter_portability(adapter)["passed"]


@pytest.mark.skipif(not _selected("zep-cloud"), reason="live Zep adapter not selected")
def test_live_zep_cloud_portability() -> None:
    api_key = os.getenv("ZEP_API_KEY")
    if not api_key:
        pytest.fail("ZEP_API_KEY is required when zep-cloud live tests are selected")
    adapter = MappedJournalSubstrateAdapter(
        ZepCloudRecordStore(
            api_key,
            base_url=os.getenv("ZEP_API_URL", "https://api.getzep.com"),
        )
    )
    assert audit_adapter_portability(adapter)["passed"]


@pytest.mark.skipif(not _selected("cognee"), reason="live Cognee adapter not selected")
def test_live_cognee_portability() -> None:
    adapter = MappedJournalSubstrateAdapter(
        CogneeRecordStore(
            os.getenv("COGNEE_BASE_URL", "http://127.0.0.1:8000"),
            api_key=os.getenv("COGNEE_API_KEY"),
        )
    )
    assert audit_adapter_portability(adapter)["passed"]
