from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from ..scenarios.schema import ExpectedMemory, Scenario
from ..telemetry.events import TraceEvent
from ..telemetry.tokens import count_tokens
from .base import TrialExecutor, format_memory_hit


class OracleTrialExecutor(TrialExecutor):
    """Scripted upper bound using evaluator annotations only for memory operations."""

    def __init__(self, provider: Any, trace: Any, **kwargs: Any):
        super().__init__(provider, "mindgraph-passive", trace, **kwargs)
        self.condition = "oracle-policy"
        self._known_uids: dict[str, str] = {}

    def run(self, scenario: Scenario) -> dict[str, Any]:
        if self.memory is None:
            raise RuntimeError("oracle-policy requires a cognitive memory backend")
        self.memory.reset()
        prior: list[dict[str, Any]] = []
        current: list[dict[str, Any]] = []
        current_session = ""
        final_answer = ""
        for event in scenario.public.events:
            if current_session and event.session_id != current_session:
                self._persist_session(scenario, current_session)
                prior.extend(current)
                current = []
            current_session = event.session_id
            current.append({"role": event.role, "content": event.content})
            context = self._oracle_retrieve(scenario, event) if event.evaluate else ""
            messages = self._build_messages(prior, current, context)
            response = self._provider_call(
                messages,
                None,
                scenario.public.scenario_id,
                event.session_id,
                event.turn_id,
            )
            if response.content:
                current.append({"role": "assistant", "content": response.content})
            if event.evaluate:
                final_answer = response.content
        self._persist_session(scenario, current_session)
        snapshot = self.memory.snapshot()
        self.metrics["memory_storage_growth"] = snapshot.get("node_count", 0) + snapshot.get(
            "edge_count", 0
        )
        return {
            "scenario_id": scenario.public.scenario_id,
            "family": scenario.public.family,
            "seed": scenario.public.seed,
            "variant": scenario.public.variant,
            "condition": self.condition,
            "answer": final_answer,
            "metrics": self.metrics,
            "memory_snapshot": snapshot,
        }

    def _persist_session(self, scenario: Scenario, session_id: str) -> None:
        items = [item for item in scenario.evaluator.durable if item.source_session == session_id]
        provenance_targets = {target for item in items for target in item.provenance}
        for item in items:
            # Claim creation can atomically create its Evidence nodes. Other
            # provenance targets (for example a failed Execution supporting a
            # Policy) remain first-class durable memories and must be written.
            if item.memory_id in provenance_targets and item.primitive == "evidence":
                continue
            evidence = [
                candidate
                for candidate in scenario.evaluator.durable
                if candidate.memory_id in item.provenance
            ]
            started = time.perf_counter()
            result = self._write_expected(item, evidence, session_id)
            self.metrics["memory_tool_calls"] += 1
            key = f"oracle_write:{item.primitive}"
            self.metrics["tool_calls_by_type"][key] = (
                self.metrics["tool_calls_by_type"].get(key, 0) + 1
            )
            self.trace.emit(
                TraceEvent(
                    "tool_call",
                    scenario.public.scenario_id,
                    self.condition,
                    session_id,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    payload={
                        "tool": "oracle_write",
                        "arguments": asdict(item),
                        "observation": result,
                    },
                )
            )

    def _write_expected(
        self, item: ExpectedMemory, evidence: list[ExpectedMemory], session_id: str
    ) -> dict[str, Any]:
        supersedes_uid = self._known_uids.get(item.supersedes or "")
        if hasattr(self.memory, "oracle_write"):
            result = self.memory.oracle_write(
                item,
                evidence=evidence,
                supersedes_uid=supersedes_uid,
                session_id=session_id,
            )
            uid = str(result.get("uid") or result.get("claim_uid") or "")
            if uid:
                self._known_uids[item.memory_id] = uid
            for expected, evidence_uid in zip(evidence, result.get("evidence_uids", [])):
                self._known_uids[expected.memory_id] = str(evidence_uid)
            if supersedes_uid and uid and item.primitive != "claim" and hasattr(
                self.memory, "oracle_link_supersedes"
            ):
                self.memory.oracle_link_supersedes(uid, supersedes_uid)
            if item.primitive != "claim" and uid and hasattr(
                self.memory, "oracle_link_provenance"
            ):
                for expected in evidence:
                    evidence_uid = self._known_uids.get(expected.memory_id)
                    if evidence_uid:
                        self.memory.oracle_link_provenance(evidence_uid, uid)
            return result

        record = self.memory.write(item.primitive, item.text, session_id, label=item.memory_id)
        self._known_uids[item.memory_id] = record.uid
        if supersedes_uid:
            older = next((row for row in self.memory.records if row.uid == supersedes_uid), None)
            if older is not None:
                older.superseded_by = record.uid
            edge = {"from_uid": record.uid, "to_uid": supersedes_uid, "edge_type": "Supersedes"}
            if edge not in self.memory.edges:
                self.memory.edges.append(edge)
        for expected in evidence:
            evidence_uid = self._known_uids.get(expected.memory_id)
            if not evidence_uid:
                ev = self.memory.write(
                    expected.primitive,
                    expected.text,
                    session_id,
                    label=expected.memory_id,
                )
                evidence_uid = ev.uid
                self._known_uids[expected.memory_id] = evidence_uid
            record.provenance.append(evidence_uid)
            self.memory.edges.append(
                {"from_uid": evidence_uid, "to_uid": record.uid, "edge_type": "Supports"}
            )
        return {"uid": record.uid, "evidence_uids": [self._known_uids[e.memory_id] for e in evidence]}

    def _oracle_retrieve(self, scenario: Scenario, event: Any) -> str:
        expected = {
            item.memory_id: item
            for item in scenario.evaluator.durable
            if item.memory_id in scenario.evaluator.expected_retrieval_ids
        }
        hits: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in expected.values():
            started = time.perf_counter()
            returned = self.memory.retrieve(item.text, self.retrieval_k)
            self.metrics["memory_tool_calls"] += 1
            self.metrics["tool_calls_by_type"]["oracle_retrieve"] = (
                self.metrics["tool_calls_by_type"].get("oracle_retrieve", 0) + 1
            )
            self.trace.emit(
                TraceEvent(
                    "retrieval",
                    scenario.public.scenario_id,
                    self.condition,
                    event.session_id,
                    event.turn_id,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    payload={
                        "query": item.text,
                        "mode": "oracle-annotated-query",
                        "candidates": returned,
                        "returned": returned,
                    },
                )
            )
            for hit in returned:
                uid = str(hit.get("uid") or hit.get("memory_id") or hit)
                if uid not in seen:
                    seen.add(uid)
                    hits.append(hit)
        context = "\n".join(format_memory_hit(hit) for hit in hits)
        self.metrics["retrieved_context_tokens"] += count_tokens(context)
        return context
