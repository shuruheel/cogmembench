from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Any, Callable

from ..scenarios.schema import ExpectedMemory


class MindGraphHTTPMemory:
    """Instrumented adapter over the actual public HTTP API."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        backend_label: str = "mindgraph-local",
        agent_id: str = "cogmembench",
        timeout: float = 60,
        trace: Callable[[dict[str, Any]], None] | None = None,
    ):
        if backend_label not in {"mindgraph-local", "mindgraph-cloud"}:
            raise ValueError("actual HTTP adapter requires mindgraph-local or mindgraph-cloud label")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.backend_label = backend_label
        self.agent_id = agent_id
        self.timeout = timeout
        self.trace = trace
        self._ingestion_telemetry: list[dict[str, Any]] = []

    def _request(self, method: str, path: str, body: Any = None) -> Any:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = None if body is None else json.dumps(body).encode()
        started = time.perf_counter()
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                result = json.loads(raw) if raw else None
                status = response.status
        except Exception as exc:
            if self.trace:
                self.trace({"kind": "http", "method": method, "path": path, "request": body, "error": repr(exc), "duration_ms": (time.perf_counter() - started) * 1000})
            raise
        if self.trace:
            self.trace({"kind": "http", "method": method, "path": path, "request": body, "response": result, "status": status, "duration_ms": (time.perf_counter() - started) * 1000})
        return result

    def reset(self) -> None:
        self._request("POST", "/clear", {"acknowledge_irreversible": True})
        self._ingestion_telemetry.clear()

    def retrieve(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        result = self._request(
            "POST",
            "/retrieve/context",
            {
                "query": query,
                "node_limit": k,
                "article_limit": 0,
                "chunk_limit": 0,
                "include_graph": True,
            },
        )
        return result.get("graph", {}).get("nodes", [])

    def retrieve_explained(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        result = self._request(
            "POST",
            "/retrieve",
            {
                "action": "hybrid",
                "query": query,
                "k": k,
                "explain": True,
                "include_sources": True,
            },
        )
        return result if isinstance(result, list) else []

    def stats(self) -> dict[str, Any]:
        result = self._request("GET", "/stats")
        return result if isinstance(result, dict) else {}

    def ingest_session(self, session_id: str, messages: list[str]) -> list[dict[str, Any]]:
        opened = self._request("POST", "/memory/session", {"action": "open", "label": session_id, "agent_id": self.agent_id})
        uid = opened.get("uid") or opened.get("session_uid")
        self._request("POST", "/memory/session", {"action": "close", "session_uid": uid, "agent_id": self.agent_id})
        job = self._request("POST", "/ingest/session", {"content": "\n".join(messages), "session_uid": uid, "agent_id": self.agent_id})
        job_id = job.get("job_id")
        if not job_id:
            return []
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            state = self._request("GET", f"/jobs/{urllib.parse.quote(job_id)}")
            status = str(state.get("status", "")).lower()
            if status in {"completed", "complete", "succeeded"}:
                result = state.get("result") if isinstance(state.get("result"), dict) else {}
                provider_telemetry = result.get("provider_telemetry")
                if isinstance(provider_telemetry, dict):
                    self._ingestion_telemetry.append(
                        {
                            "session_id": session_id,
                            "job_id": job_id,
                            **provider_telemetry,
                        }
                    )
                return []
            if status in {"failed", "cancelled"}:
                raise RuntimeError(f"MindGraph ingestion failed: {state}")
            time.sleep(0.25)
        raise TimeoutError(f"MindGraph ingestion job {job_id} did not finish")

    def provider_telemetry(self) -> dict[str, Any]:
        """Aggregate server-reported provider usage without estimating missing tokens."""
        numeric_paths = {
            "mindgraph_extraction_requests": ("extraction", "requests"),
            "mindgraph_extraction_responses": ("extraction", "responses"),
            "mindgraph_extraction_failed_requests": ("extraction", "failed_requests"),
            "mindgraph_extraction_usage_reported_responses": (
                "extraction",
                "usage_reported_responses",
            ),
            "mindgraph_extraction_input_tokens": ("extraction", "prompt_tokens"),
            "mindgraph_extraction_output_tokens": ("extraction", "completion_tokens"),
            "mindgraph_extraction_total_tokens": ("extraction", "total_tokens"),
            "mindgraph_embedding_requests": ("embedding", "requests"),
            "mindgraph_embedding_responses": ("embedding", "responses"),
            "mindgraph_embedding_failed_requests": ("embedding", "failed_requests"),
            "mindgraph_embedding_input_items": ("embedding", "submitted_input_items"),
            "mindgraph_embedding_input_chars": ("embedding", "submitted_input_chars"),
            "mindgraph_embedding_output_vectors": ("embedding", "output_vectors"),
        }
        metrics: dict[str, int] = {name: 0 for name in numeric_paths}
        for job in self._ingestion_telemetry:
            for name, (section, field) in numeric_paths.items():
                value = job.get(section, {}).get(field, 0)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    metrics[name] += int(value)
        extraction_responses = metrics["mindgraph_extraction_responses"]
        reported_responses = metrics["mindgraph_extraction_usage_reported_responses"]
        return {
            "metrics": metrics,
            "extraction_token_usage_complete": extraction_responses == reported_responses,
            "embedding_token_usage_available": False,
            "jobs": list(self._ingestion_telemetry),
        }

    def execute_tool(self, name: str, args: dict[str, Any], session_id: str) -> Any:
        payload = {**args, "agent_id": self.agent_id}
        action = str(args.get("action", ""))
        if name == "mindgraph_retrieve":
            return {"results": self.retrieve(str(args.get("query", "")), int(args.get("limit", 5)))}
        if name == "mindgraph_capture":
            if action == "preference":
                return self._request("POST", "/memory/config", {"action": "set_preference", "label": args.get("label", "preference"), "summary": args.get("summary", ""), "agent_id": self.agent_id})
            return self._request("POST", "/reality/capture", {"action": "observation", "label": args.get("label", ""), "summary": args.get("summary", ""), "agent_id": self.agent_id})
        if name == "mindgraph_reason":
            claim = {"label": args.get("label", ""), "content": args.get("summary", ""), "confidence": args.get("confidence", 0.7)}
            return self._request("POST", "/epistemic/argument", {"claim": claim, "evidence": [], "agent_id": self.agent_id})
        if name == "mindgraph_commit":
            endpoint = "/intent/deliberation" if "decision" in action else "/intent/commitment"
            server_action = "open_decision" if "decision" in action else ("project" if action == "project" else "goal")
            return self._request("POST", endpoint, {**payload, "action": server_action})
        if name == "mindgraph_plan":
            if "execution" in action:
                execution_uid = args.get("execution_uid")
                if execution_uid:
                    return self._request(
                        "POST",
                        "/agent/execution",
                        {
                            **payload,
                            "action": "fail",
                            "execution_uid": execution_uid,
                            "props": {"error": args.get("summary", "")},
                        },
                    )
                # A failure without an existing Execution cannot use the server's
                # fail transition. Preserve it as a failed task instead of issuing
                # an invalid lifecycle mutation.
                return self._request(
                    "POST",
                    "/agent/plan",
                    {
                        **payload,
                        "action": "create_task",
                        "props": {"status": "failed", "description": args.get("summary", "")},
                    },
                )
            if "policy" in action:
                return self._request("POST", "/agent/governance", {**payload, "action": "create_policy"})
            return self._request("POST", "/agent/plan", {**payload, "action": "create_task"})
        raise ValueError(f"unsupported tool {name}")

    def oracle_write(
        self,
        item: ExpectedMemory,
        *,
        evidence: list[ExpectedMemory],
        supersedes_uid: str | None,
        session_id: str,
    ) -> dict[str, Any]:
        common = {
            "label": item.memory_id,
            "summary": item.text,
            "agent_id": self.agent_id,
        }
        if item.primitive == "preference":
            return self._request(
                "POST", "/memory/config", {**common, "action": "set_preference"}
            )
        if item.primitive == "claim":
            result = self._request(
                "POST",
                "/epistemic/argument",
                {
                    "claim": {
                        "label": item.memory_id,
                        "props": {"content": item.text, "source": "oracle-policy"},
                    },
                    "evidence": [
                        {
                            "label": expected.memory_id,
                            "props": {
                                "description": expected.text,
                            },
                        }
                        for expected in evidence
                    ],
                    "supersedes_uid": supersedes_uid,
                    "agent_id": self.agent_id,
                },
            )
            return {"uid": result.get("claim_uid"), **result}
        if item.primitive == "goal":
            return self._request(
                "POST", "/intent/commitment", {**common, "action": "goal"}
            )
        if item.primitive == "decision":
            return self._request(
                "POST", "/intent/deliberation", {**common, "action": "open_decision"}
            )
        if item.primitive == "task":
            return self._request(
                "POST",
                "/agent/plan",
                {
                    **common,
                    "action": "create_task",
                    "props": {"description": item.text, "status": item.value or None},
                },
            )
        if item.primitive == "execution":
            started = self._request(
                "POST", "/agent/execution", {**common, "action": "start"}
            )
            uid = started.get("uid") or started.get("execution_uid")
            return self._request(
                "POST",
                "/agent/execution",
                {
                    "action": "fail",
                    "execution_uid": uid,
                    "props": {"error": item.text},
                    "agent_id": self.agent_id,
                },
            )
        if item.primitive == "policy":
            return self._request(
                "POST", "/agent/governance", {**common, "action": "create_policy"}
            )
        raise ValueError(f"oracle-policy has no primitive mapping for {item.primitive}")

    def _oracle_link(self, from_uid: str, to_uid: str, props: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/edge",
            {
                "from_uid": from_uid,
                "to_uid": to_uid,
                "props": props,
                "agent_id": self.agent_id,
            },
        )

    def oracle_link_provenance(self, source_uid: str, derived_uid: str) -> dict[str, Any]:
        return self._oracle_link(
            source_uid,
            derived_uid,
            {"_type": "Supports", "strength": 1.0, "support_type": "oracle-policy"},
        )

    def oracle_link_supersedes(self, newer_uid: str, older_uid: str) -> dict[str, Any]:
        return self._oracle_link(
            newer_uid,
            older_uid,
            {"_type": "Supersedes", "supersession_type": "explicit_correction"},
        )

    def snapshot(self) -> dict[str, Any]:
        stats = self._request("GET", "/stats")
        nodes = self._request("GET", "/nodes?limit=1000&offset=0")
        node_rows = nodes.get("items", nodes) if isinstance(nodes, dict) else nodes
        edges = self._request(
            "POST",
            "/edges/batch",
            {"uids": [row["uid"] for row in node_rows if row.get("uid")]},
        )
        return {
            "backend": self.backend_label,
            "stats": stats,
            "records": node_rows,
            "edges": edges,
            "node_count": stats.get("total_nodes", stats.get("node_count", len(node_rows))),
            "edge_count": stats.get("total_edges", stats.get("edge_count", 0)),
        }
