from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from cogmembench.scenarios.schema import Event
from cogmembench.substrate import (
    CogneeRecordStore,
    ExternalRecord,
    MappedJournalSubstrateAdapter,
    Mem0OSSRecordStore,
    MindGraphRecordStore,
    ZepCloudRecordStore,
)
from cogmembench.validation import validate_adapter_contract


class FakeRecordStore:
    store_name = "fake-external-mapped"
    store_version = "1"
    asynchronous = False
    max_search_results = 50

    def __init__(self) -> None:
        self.records: dict[str, list[ExternalRecord]] = {}

    def reset_namespace(self, namespace: str) -> None:
        self.records[namespace] = []

    def put_record(
        self,
        namespace: str,
        record_id: str,
        content: str,
        metadata: dict[str, Any],
        *,
        infer: bool,
    ) -> ExternalRecord:
        row = ExternalRecord(record_id, content, metadata)
        self.records.setdefault(namespace, []).append(row)
        return row

    def list_records(self, namespace: str) -> list[ExternalRecord]:
        return list(self.records.get(namespace, ()))

    def search_records(
        self, namespace: str, query: str, limit: int
    ) -> list[ExternalRecord]:
        terms = set(query.lower().split())
        rows = []
        for row in self.records.get(namespace, ()):
            overlap = len(terms & set(row.content.lower().split()))
            if overlap:
                rows.append(replace(row, score=float(overlap)))
        return sorted(rows, key=lambda row: -row.score)[:limit]

    def quiesce(self) -> None:
        return None


class FakeTransport:
    def __init__(self, responses: list[Any] | None = None) -> None:
        self.responses = list(responses or [])
        self.calls: list[tuple[str, str, Any, bool]] = []

    def request(
        self,
        method: str,
        path: str,
        body: Any = None,
        *,
        allow_not_found: bool = False,
    ) -> Any:
        self.calls.append((method, path, body, allow_not_found))
        return self.responses.pop(0) if self.responses else None

    def request_multipart(self, path: str, fields: dict[str, str]) -> Any:
        self.calls.append(("MULTIPART", path, fields, False))
        return self.responses.pop(0) if self.responses else None


def test_mapped_external_journal_passes_full_contract_without_sidecar() -> None:
    result = validate_adapter_contract(MappedJournalSubstrateAdapter(FakeRecordStore()))

    assert result["passed"]
    assert result["adapter"] == "fake-external-mapped"


def test_native_observation_is_recovered_from_remote_metadata() -> None:
    store = FakeRecordStore()
    adapter = MappedJournalSubstrateAdapter(store)
    adapter.reset("native-world")
    event = Event(
        "s1",
        1,
        "user",
        "The alpha limit is 100",
        event_time=5,
        report_time=10,
        event_id="event-1",
        phase="accumulate",
    )

    observed = adapter.observe(event, 10)
    recovered = adapter.snapshot(valid_at=5, known_at=10)

    assert observed.content == event.content
    assert [row.content for row in recovered.artifacts] == [event.content]
    assert store.records["native-world"][0].metadata["cogmembench_event"]


def test_mem0_oss_uses_scoped_delete_and_infer_flag() -> None:
    transport = FakeTransport()
    store = Mem0OSSRecordStore(transport=transport)

    store.reset_namespace("trial one")
    store.put_record("trial one", "r1", "hello", {"k": "v"}, infer=False)

    assert transport.calls[0][0] == "DELETE"
    assert "user_id=trial+one" in transport.calls[0][1]
    assert transport.calls[1][2]["infer"] is False


def test_zep_uses_dedicated_graph_and_episode_scope() -> None:
    transport = FakeTransport([None, {}, {"uuid": "ep-1", "processed": True}, {"episodes": []}])
    store = ZepCloudRecordStore("key", transport=transport)

    store.reset_namespace("trial")
    store.put_record("trial", "r1", "hello", {"k": "v"}, infer=False)
    store.search_records("trial", "hello", 5)

    assert transport.calls[0][:2] == ("DELETE", "/api/v2/graph/cogmembench-trial")
    assert transport.calls[1][1] == "/api/v2/graph/create"
    assert transport.calls[2][2]["graph_id"] == "cogmembench-trial"
    assert transport.calls[3][2]["scope"] == "episodes"


def test_mindgraph_reset_is_namespace_scoped_not_global_clear() -> None:
    transport = FakeTransport()
    store = MindGraphRecordStore(transport=transport)

    store.reset_namespace("trial")
    store.put_record("trial", "r1", "hello", {"k": "v"}, infer=False)

    assert transport.calls[0][1] == "/nodes/delete"
    assert transport.calls[0][2]["agent_id"] == "cogmembench-v2:trial"
    assert all(path != "/clear" for _, path, _, _ in transport.calls)
    assert transport.calls[1][2]["props"]["type_name"] == "CogMemBenchRecord"


def test_cognee_uses_scoped_dataset_and_raw_record_wrapper() -> None:
    transport = FakeTransport(
        [
            [],
            {"id": "dataset-1", "name": "cogmembench-trial"},
            {},
            {},
            [{"id": "data-1"}],
            json.dumps(
                {
                    "schema": "cogmembench.cognee-record.v1",
                    "record_id": "r1",
                    "content": "hello",
                    "metadata": {"k": "v"},
                }
            ),
        ]
    )
    store = CogneeRecordStore(transport=transport)

    store.reset_namespace("trial")
    store.put_record("trial", "r1", "hello", {"k": "v"}, infer=False)
    rows = store.list_records("trial")

    assert transport.calls[1][:2] == ("POST", "/api/v1/datasets/")
    assert transport.calls[2][:2] == ("MULTIPART", "/api/v1/add")
    assert transport.calls[3][1] == "/api/v1/cognify"
    assert rows == [ExternalRecord("r1", "hello", {"k": "v"})]
