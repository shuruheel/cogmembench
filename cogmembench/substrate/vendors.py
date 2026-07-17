from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol

from .external import ExternalRecord


class JSONTransport(Protocol):
    def request(
        self,
        method: str,
        path: str,
        body: Any = None,
        *,
        allow_not_found: bool = False,
    ) -> Any: ...


class HTTPJSONTransport:
    def __init__(
        self,
        base_url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {"Content-Type": "application/json", **(headers or {})}
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        body: Any = None,
        *,
        allow_not_found: bool = False,
    ) -> Any:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers=self.headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                if not raw:
                    return None
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return raw.decode(errors="replace")
        except urllib.error.HTTPError as exc:
            if allow_not_found and exc.code == 404:
                return None
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(
                f"{method} {path} returned HTTP {exc.code}: {detail[:1000]}"
            ) from exc

    def request_multipart(self, path: str, fields: dict[str, str]) -> Any:
        boundary = f"cogmembench-{time.time_ns()}"
        chunks: list[bytes] = []
        for name, value in fields.items():
            chunks.extend(
                (
                    f"--{boundary}\r\n".encode(),
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                    value.encode(),
                    b"\r\n",
                )
            )
        chunks.append(f"--{boundary}--\r\n".encode())
        headers = {
            key: value for key, value in self.headers.items() if key.lower() != "content-type"
        }
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        request = urllib.request.Request(
            self.base_url + path,
            data=b"".join(chunks),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(
                f"POST {path} returned HTTP {exc.code}: {detail[:1000]}"
            ) from exc


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if not isinstance(value, dict):
        return []
    for key in ("results", "memories", "episodes", "items", "data"):
        nested = value.get(key)
        if isinstance(nested, list):
            return [row for row in nested if isinstance(row, dict)]
        if isinstance(nested, dict):
            for child in ("results", "memories", "episodes", "items"):
                rows = nested.get(child)
                if isinstance(rows, list):
                    return [row for row in rows if isinstance(row, dict)]
    return []


def _content(row: dict[str, Any]) -> str:
    return str(row.get("memory") or row.get("text") or row.get("content") or "")


class Mem0OSSRecordStore:
    """Exact-record mapping over the official self-hosted Mem0 REST API."""

    store_name = "mem0-oss-mapped"
    store_version = "rest-1.x"
    asynchronous = False
    max_search_results = 50

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        *,
        api_key: str | None = None,
        timeout: float = 120,
        transport: JSONTransport | None = None,
    ) -> None:
        headers = {"X-API-Key": api_key} if api_key else {}
        self.http = transport or HTTPJSONTransport(
            base_url, headers=headers, timeout=timeout
        )

    @staticmethod
    def _query(namespace: str) -> str:
        return urllib.parse.urlencode({"user_id": namespace})

    @staticmethod
    def _record(row: dict[str, Any]) -> ExternalRecord:
        metadata = dict(row.get("metadata") or {})
        record_id = str(
            metadata.get("cogmembench_record_id") or row.get("id") or row.get("memory_id")
        )
        score = row.get("score", 0.0)
        return ExternalRecord(
            record_id,
            _content(row),
            metadata,
            float(score) if isinstance(score, (int, float)) else 0.0,
        )

    def reset_namespace(self, namespace: str) -> None:
        self.http.request(
            "DELETE",
            f"/memories?{self._query(namespace)}",
            allow_not_found=True,
        )

    def put_record(
        self,
        namespace: str,
        record_id: str,
        content: str,
        metadata: dict[str, Any],
        *,
        infer: bool,
    ) -> ExternalRecord:
        self.http.request(
            "POST",
            "/memories",
            {
                "messages": [{"role": "user", "content": content}],
                "user_id": namespace,
                "metadata": metadata,
                "infer": infer,
            },
        )
        return ExternalRecord(record_id, content, metadata)

    def list_records(self, namespace: str) -> list[ExternalRecord]:
        result = self.http.request("GET", f"/memories?{self._query(namespace)}")
        return [self._record(row) for row in _rows(result)]

    def search_records(
        self, namespace: str, query: str, limit: int
    ) -> list[ExternalRecord]:
        result = self.http.request(
            "POST",
            "/search",
            {"query": query, "user_id": namespace, "limit": min(limit, 50)},
        )
        return [self._record(row) for row in _rows(result)]

    def quiesce(self) -> None:
        return None


class ZepCloudRecordStore:
    """Mapped episode journal over Zep's v2 Graph API."""

    store_name = "zep-cloud-mapped"
    store_version = "graph-api-v2"
    asynchronous = True
    max_search_results = 50

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.getzep.com",
        timeout: float = 180,
        quiesce_timeout: float = 300,
        transport: JSONTransport | None = None,
    ) -> None:
        self.http = transport or HTTPJSONTransport(
            base_url,
            headers={"Authorization": f"Api-Key {api_key}"},
            timeout=timeout,
        )
        self.quiesce_timeout = quiesce_timeout
        self._pending_episode_ids: list[str] = []

    @staticmethod
    def _graph_id(namespace: str) -> str:
        safe = "".join(char if char.isalnum() or char in "-_" else "-" for char in namespace)
        return f"cogmembench-{safe}"[:120]

    @staticmethod
    def _record(row: dict[str, Any]) -> ExternalRecord:
        metadata = dict(row.get("metadata") or {})
        record_id = str(metadata.get("cogmembench_record_id") or row.get("uuid") or "")
        score = row.get("score", row.get("relevance", 0.0))
        return ExternalRecord(
            record_id,
            _content(row),
            metadata,
            float(score) if isinstance(score, (int, float)) else 0.0,
        )

    def reset_namespace(self, namespace: str) -> None:
        graph_id = urllib.parse.quote(self._graph_id(namespace), safe="")
        self.http.request(
            "DELETE", f"/api/v2/graph/{graph_id}", allow_not_found=True
        )
        self.http.request(
            "POST",
            "/api/v2/graph/create",
            {"graph_id": self._graph_id(namespace), "name": namespace},
        )
        self._pending_episode_ids.clear()

    def put_record(
        self,
        namespace: str,
        record_id: str,
        content: str,
        metadata: dict[str, Any],
        *,
        infer: bool,
    ) -> ExternalRecord:
        result = self.http.request(
            "POST",
            "/api/v2/graph",
            {
                "graph_id": self._graph_id(namespace),
                "type": "text",
                "data": content,
                "metadata": metadata,
                "source_description": "CogMemBench mapped record",
            },
        )
        if isinstance(result, dict):
            episode_id = result.get("uuid")
            if episode_id and not result.get("processed", False):
                self._pending_episode_ids.append(str(episode_id))
        return ExternalRecord(record_id, content, metadata)

    def list_records(self, namespace: str) -> list[ExternalRecord]:
        graph_id = urllib.parse.quote(self._graph_id(namespace), safe="")
        query = urllib.parse.urlencode({"lastn": 1000})
        result = self.http.request(
            "GET", f"/api/v2/graph/episodes/graph/{graph_id}?{query}"
        )
        return [self._record(row) for row in _rows(result)]

    def search_records(
        self, namespace: str, query: str, limit: int
    ) -> list[ExternalRecord]:
        result = self.http.request(
            "POST",
            "/api/v2/graph/search",
            {
                "graph_id": self._graph_id(namespace),
                "query": query[:400],
                "scope": "episodes",
                "limit": min(limit, 50),
            },
        )
        return [self._record(row) for row in _rows(result)]

    def quiesce(self) -> None:
        deadline = time.time() + self.quiesce_timeout
        while self._pending_episode_ids:
            episode_id = self._pending_episode_ids[0]
            result = self.http.request(
                "GET", f"/api/v2/graph/episodes/{urllib.parse.quote(episode_id, safe='')}"
            )
            if isinstance(result, dict) and result.get("processed"):
                self._pending_episode_ids.pop(0)
                continue
            if time.time() >= deadline:
                raise TimeoutError(f"Zep episode {episode_id} did not quiesce")
            time.sleep(0.25)


class CogneeRecordStore:
    """Exact mapped records over Cognee's dataset, ingestion, and search APIs."""

    store_name = "cognee-mapped"
    store_version = "rest-api-v1"
    asynchronous = False
    max_search_results = 100

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        *,
        api_key: str | None = None,
        timeout: float = 300,
        transport: JSONTransport | None = None,
    ) -> None:
        headers = {"X-Api-Key": api_key} if api_key else {}
        self.http = transport or HTTPJSONTransport(
            base_url, headers=headers, timeout=timeout
        )
        self._dataset_ids: dict[str, str] = {}

    @staticmethod
    def _dataset_name(namespace: str) -> str:
        safe = "".join(char if char.isalnum() or char in "-_" else "-" for char in namespace)
        return f"cogmembench-{safe}"[:120]

    @staticmethod
    def _dataset_rows(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict):
            for key in ("datasets", "data", "results"):
                if isinstance(value.get(key), list):
                    return [row for row in value[key] if isinstance(row, dict)]
        return []

    def _dataset_id(self, namespace: str) -> str:
        if namespace in self._dataset_ids:
            return self._dataset_ids[namespace]
        name = self._dataset_name(namespace)
        datasets = self._dataset_rows(self.http.request("GET", "/api/v1/datasets/"))
        match = next((row for row in datasets if row.get("name") == name), None)
        if match is None:
            raise RuntimeError(f"Cognee dataset not found after reset: {name}")
        dataset_id = str(match.get("id") or match.get("dataset_id") or "")
        if not dataset_id:
            raise RuntimeError(f"Cognee dataset has no id: {match}")
        self._dataset_ids[namespace] = dataset_id
        return dataset_id

    @staticmethod
    def _decode_record(value: Any, fallback_id: str = "") -> ExternalRecord | None:
        if isinstance(value, dict) and "raw_data" in value:
            value = value["raw_data"]
        if isinstance(value, bytes):
            value = value.decode(errors="replace")
        if not isinstance(value, str):
            return None
        try:
            wrapper = json.loads(value)
        except json.JSONDecodeError:
            return ExternalRecord(fallback_id, value, {})
        if not isinstance(wrapper, dict) or wrapper.get("schema") != "cogmembench.cognee-record.v1":
            return ExternalRecord(fallback_id, value, {})
        return ExternalRecord(
            str(wrapper.get("record_id") or fallback_id),
            str(wrapper.get("content") or ""),
            dict(wrapper.get("metadata") or {}),
        )

    def reset_namespace(self, namespace: str) -> None:
        name = self._dataset_name(namespace)
        datasets = self._dataset_rows(self.http.request("GET", "/api/v1/datasets/"))
        for row in datasets:
            if row.get("name") != name:
                continue
            dataset_id = str(row.get("id") or row.get("dataset_id") or "")
            if dataset_id:
                self.http.request(
                    "DELETE",
                    f"/api/v1/datasets/{urllib.parse.quote(dataset_id, safe='')}",
                    allow_not_found=True,
                )
        created = self.http.request("POST", "/api/v1/datasets/", {"name": name})
        dataset_id = ""
        if isinstance(created, dict):
            dataset_id = str(created.get("id") or created.get("dataset_id") or "")
        self._dataset_ids.pop(namespace, None)
        if dataset_id:
            self._dataset_ids[namespace] = dataset_id

    def put_record(
        self,
        namespace: str,
        record_id: str,
        content: str,
        metadata: dict[str, Any],
        *,
        infer: bool,
    ) -> ExternalRecord:
        wrapper = json.dumps(
            {
                "schema": "cogmembench.cognee-record.v1",
                "record_id": record_id,
                "content": content,
                "metadata": metadata,
                "native_inference_requested": infer,
            },
            sort_keys=True,
        )
        multipart = getattr(self.http, "request_multipart", None)
        if multipart is None:
            raise RuntimeError("Cognee transport must implement request_multipart")
        multipart(
            "/api/v1/add",
            {"data": wrapper, "datasetName": self._dataset_name(namespace)},
        )
        self.http.request(
            "POST",
            "/api/v1/cognify",
            {"datasets": [self._dataset_name(namespace)], "run_in_background": False},
        )
        return ExternalRecord(record_id, content, metadata)

    def list_records(self, namespace: str) -> list[ExternalRecord]:
        dataset_id = self._dataset_id(namespace)
        result = self.http.request(
            "GET", f"/api/v1/datasets/{urllib.parse.quote(dataset_id, safe='')}/data"
        )
        records = []
        for item in _rows(result) or self._dataset_rows(result):
            data_id = str(item.get("id") or item.get("data_id") or "")
            if not data_id:
                continue
            raw = self.http.request(
                "GET",
                "/api/v1/datasets/"
                f"{urllib.parse.quote(dataset_id, safe='')}/data/"
                f"{urllib.parse.quote(data_id, safe='')}/raw",
            )
            record = self._decode_record(raw, data_id)
            if record is not None:
                records.append(record)
        return records

    @classmethod
    def _search_rows(cls, value: Any) -> list[dict[str, Any]]:
        direct = _rows(value)
        expanded = []
        for row in direct:
            nested = row.get("search_result")
            if isinstance(nested, list):
                expanded.extend(item for item in nested if isinstance(item, dict))
            elif isinstance(nested, dict):
                expanded.append(nested)
            else:
                expanded.append(row)
        return expanded

    def search_records(
        self, namespace: str, query: str, limit: int
    ) -> list[ExternalRecord]:
        result = self.http.request(
            "POST",
            "/api/v1/search",
            {
                "search_type": "CHUNKS_LEXICAL",
                "datasets": [self._dataset_name(namespace)],
                "query": query,
                "top_k": min(limit, self.max_search_results),
            },
        )
        records = []
        for row in self._search_rows(result):
            decoded = self._decode_record(row.get("text"), str(row.get("id") or ""))
            if decoded is not None:
                score = row.get("score", row.get("similarity", 0.0))
                records.append(
                    ExternalRecord(
                        decoded.record_id,
                        decoded.content,
                        decoded.metadata,
                        float(score) if isinstance(score, (int, float)) else 0.0,
                    )
                )
        return records[:limit]

    def quiesce(self) -> None:
        return None


class MindGraphRecordStore:
    """Namespace-scoped mapping over MindGraph's public node/search API."""

    store_name = "mindgraph-v2-mapped"
    store_version = "public-http-v2"
    asynchronous = False
    max_search_results = 100

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:18790",
        *,
        api_key: str | None = None,
        timeout: float = 120,
        transport: JSONTransport | None = None,
    ) -> None:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.http = transport or HTTPJSONTransport(
            base_url, headers=headers, timeout=timeout
        )

    @staticmethod
    def _agent_id(namespace: str) -> str:
        return f"cogmembench-v2:{namespace}"

    @staticmethod
    def _record(row: dict[str, Any], score: float = 0.0) -> ExternalRecord | None:
        node = row.get("node") if isinstance(row.get("node"), dict) else row
        props = node.get("props") if isinstance(node.get("props"), dict) else {}
        metadata: dict[str, Any] = {}
        content = str(node.get("summary") or node.get("label") or "")
        if props.get("_type") == "Custom" or "data" in props:
            data = props.get("data") if isinstance(props.get("data"), dict) else props
            metadata = dict(data.get("metadata") or {})
            content = str(data.get("content") or content)
        elif props.get("_type") == "Observation" or "observation_type" in props:
            encoded = props.get("content")
            try:
                wrapper = json.loads(str(encoded))
            except (json.JSONDecodeError, TypeError):
                wrapper = {}
            if isinstance(wrapper, dict):
                metadata = dict(wrapper.get("metadata") or {})
                content = str(wrapper.get("content") or content)
        record_id = str(metadata.get("cogmembench_record_id") or node.get("label") or "")
        if not record_id:
            return None
        actual_score = row.get("score", score)
        return ExternalRecord(
            record_id,
            content,
            metadata,
            float(actual_score) if isinstance(actual_score, (int, float)) else 0.0,
        )

    def reset_namespace(self, namespace: str) -> None:
        self.http.request(
            "POST",
            "/nodes/delete",
            {
                "agent_id": self._agent_id(namespace),
                "reason": "cogmembench namespace reset",
                "by": "cogmembench",
                "hard_purge": True,
            },
        )

    def put_record(
        self,
        namespace: str,
        record_id: str,
        content: str,
        metadata: dict[str, Any],
        *,
        infer: bool,
    ) -> ExternalRecord:
        if infer:
            wrapper = json.dumps({"content": content, "metadata": metadata}, sort_keys=True)
            self.http.request(
                "POST",
                "/reality/capture",
                {
                    "action": "observation",
                    "label": record_id,
                    "summary": content,
                    "agent_id": self._agent_id(namespace),
                    "props": {
                        "observation_type": "cogmembench_native_event",
                        "content": wrapper,
                        "timestamp": metadata.get("cogmembench_logical_time"),
                    },
                },
            )
        else:
            self.http.request(
                "POST",
                "/node",
                {
                    "label": record_id,
                    "summary": content,
                    "agent_id": self._agent_id(namespace),
                    "props": {
                        "_type": "Custom",
                        "type_name": "CogMemBenchRecord",
                        "layer": "memory",
                        "data": {"content": content, "metadata": metadata},
                    },
                },
            )
        return ExternalRecord(record_id, content, metadata)

    def list_records(self, namespace: str) -> list[ExternalRecord]:
        agent = urllib.parse.quote(self._agent_id(namespace), safe="")
        result = self.http.request("GET", f"/nodes?agent={agent}&limit=100000")
        return [record for row in _rows(result) if (record := self._record(row)) is not None]

    def search_records(
        self, namespace: str, query: str, limit: int
    ) -> list[ExternalRecord]:
        result = self.http.request(
            "POST",
            "/search",
            {"query": query, "limit": min(max(limit * 4, limit), 400)},
        )
        rows = _rows(result)
        records = [record for row in rows if (record := self._record(row)) is not None]
        return [
            record
            for record in records
            if record.metadata.get("cogmembench_namespace") == namespace
        ][:limit]

    def quiesce(self) -> None:
        return None
