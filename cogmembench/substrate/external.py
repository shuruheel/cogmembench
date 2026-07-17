from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from typing import Any, Protocol

from ..scenarios.schema import Event
from .adapter import (
    CapabilityManifest,
    ClockMode,
    ClockOrderError,
    EvidenceMode,
    IsolationError,
    RetrievalBudget,
    RetrievalResult,
    RetrievedArtifact,
    SnapshotResult,
    UsageFidelity,
    UsageReport,
)
from .schema import (
    ArtifactKind,
    AuditReceipt,
    CognitiveArtifact,
    CognitiveRelation,
    EpistemicStatus,
    RelationKind,
    TimeInterval,
    Visibility,
)

JOURNAL_SCHEMA = "cogmembench.external-journal.v2"
NATIVE_EVENT_SCHEMA = "cogmembench.native-event.v2"
WORD = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class ExternalRecord:
    record_id: str
    content: str
    metadata: dict[str, Any]
    score: float = 0.0


class ExternalRecordStore(Protocol):
    store_name: str
    store_version: str
    asynchronous: bool
    max_search_results: int

    def reset_namespace(self, namespace: str) -> None: ...

    def put_record(
        self,
        namespace: str,
        record_id: str,
        content: str,
        metadata: dict[str, Any],
        *,
        infer: bool,
    ) -> ExternalRecord: ...

    def list_records(self, namespace: str) -> list[ExternalRecord]: ...

    def search_records(
        self, namespace: str, query: str, limit: int
    ) -> list[ExternalRecord]: ...

    def quiesce(self) -> None: ...


def _interval_to_dict(value: TimeInterval | None) -> dict[str, int | None] | None:
    return None if value is None else {"start": value.start, "end": value.end}


def _interval_from_dict(value: dict[str, Any] | None) -> TimeInterval | None:
    if value is None:
        return None
    return TimeInterval(int(value["start"]), int(value["end"]) if value.get("end") is not None else None)


def _artifact_to_dict(artifact: CognitiveArtifact) -> dict[str, Any]:
    return {
        "artifact_id": artifact.artifact_id,
        "kind": artifact.kind.value,
        "content": artifact.content,
        "scenario_id": artifact.scenario_id,
        "valid_time": _interval_to_dict(artifact.valid_time),
        "transaction_time": _interval_to_dict(artifact.transaction_time),
        "structured_content": artifact.structured_content,
        "entity_scope": list(artifact.entity_scope),
        "epistemic_status": artifact.epistemic_status.value,
        "confidence": artifact.confidence,
        "actor_id": artifact.actor_id,
        "session_id": artifact.session_id,
        "turn_id": artifact.turn_id,
        "provenance_event_ids": list(artifact.provenance_event_ids),
        "revision_of": artifact.revision_of,
        "visibility": artifact.visibility.value,
    }


def _artifact_from_dict(value: dict[str, Any]) -> CognitiveArtifact:
    valid_time = _interval_from_dict(value["valid_time"])
    if valid_time is None:
        raise ValueError("artifact valid_time is required")
    return CognitiveArtifact(
        artifact_id=str(value["artifact_id"]),
        kind=ArtifactKind(value["kind"]),
        content=str(value["content"]),
        scenario_id=str(value["scenario_id"]),
        valid_time=valid_time,
        transaction_time=_interval_from_dict(value.get("transaction_time")),
        structured_content=dict(value.get("structured_content", {})),
        entity_scope=tuple(str(item) for item in value.get("entity_scope", ())),
        epistemic_status=EpistemicStatus(value.get("epistemic_status", "proposed")),
        confidence=(
            float(value["confidence"]) if value.get("confidence") is not None else None
        ),
        actor_id=str(value.get("actor_id", "")),
        session_id=str(value.get("session_id", "")),
        turn_id=(int(value["turn_id"]) if value.get("turn_id") is not None else None),
        provenance_event_ids=tuple(
            str(item) for item in value.get("provenance_event_ids", ())
        ),
        revision_of=(str(value["revision_of"]) if value.get("revision_of") else None),
        visibility=Visibility(value.get("visibility", "agent")),
    )


def _relation_to_dict(relation: CognitiveRelation) -> dict[str, Any]:
    data = asdict(relation)
    data["kind"] = relation.kind.value
    data["valid_time"] = _interval_to_dict(relation.valid_time)
    return data


def _relation_from_dict(value: dict[str, Any]) -> CognitiveRelation:
    return CognitiveRelation(
        relation_id=str(value["relation_id"]),
        source_id=str(value["source_id"]),
        kind=RelationKind(value["kind"]),
        target_id=str(value["target_id"]),
        created_at=int(value["created_at"]),
        valid_time=_interval_from_dict(value.get("valid_time")),
        strength=(float(value["strength"]) if value.get("strength") is not None else None),
        source=str(value.get("source", "")),
        metadata=dict(value.get("metadata", {})),
    )


class MappedJournalSubstrateAdapter:
    """Persist the canonical operation journal inside an external memory system.

    The remote store is the source of truth. No local sidecar is consulted for snapshots,
    retrieval, reset verification, or audit export.
    """

    def __init__(
        self,
        store: ExternalRecordStore,
        *,
        native_automatic_capture: bool = True,
        audit_export: bool = True,
    ) -> None:
        self.store = store
        self.native_automatic_capture = native_automatic_capture
        self.audit_export_enabled = audit_export
        self._namespace: str | None = None
        self._last_logical_time = 0
        self._reads = 0
        self._writes = 0

    @property
    def namespace(self) -> str:
        if self._namespace is None:
            raise IsolationError("reset(namespace) must be called before using the adapter")
        return self._namespace

    def _advance(self, logical_time: int) -> None:
        if isinstance(logical_time, bool) or not isinstance(logical_time, int) or logical_time < 0:
            raise ClockOrderError("logical_time must be a non-negative integer")
        if logical_time < self._last_logical_time:
            raise ClockOrderError(
                f"logical time moved backward: {logical_time} < {self._last_logical_time}"
            )
        self._last_logical_time = logical_time

    def reset(self, namespace: str) -> None:
        if not namespace.strip():
            raise IsolationError("namespace must be non-empty")
        self.store.reset_namespace(namespace)
        self._namespace = namespace
        self._last_logical_time = 0
        self._reads = 0
        self._writes = 0

    def quiesce(self) -> None:
        self.store.quiesce()

    def close_session(self, session_id: str, logical_time: int) -> None:
        self._advance(logical_time)
        self._append(
            "close_session",
            logical_time,
            {"session_id": session_id},
        )

    @staticmethod
    def _record_digest(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def _append(self, operation: str, logical_time: int, data: dict[str, Any]) -> str:
        payload = {
            "schema": JOURNAL_SCHEMA,
            "namespace": self.namespace,
            "operation": operation,
            "logical_time": logical_time,
            "data": data,
        }
        record_id = f"cogmem:{self._record_digest(payload)}"
        envelope = {**payload, "record_id": record_id}
        content = json.dumps(envelope, sort_keys=True, ensure_ascii=False)
        metadata = {
            "cogmembench_schema": JOURNAL_SCHEMA,
            "cogmembench_namespace": self.namespace,
            "cogmembench_record_id": record_id,
            "cogmembench_operation": operation,
            "cogmembench_logical_time": logical_time,
        }
        existing = {row.record_id for row in self.store.list_records(self.namespace)}
        self._reads += 1
        if record_id not in existing:
            self.store.put_record(
                self.namespace,
                record_id,
                content,
                metadata,
                infer=False,
            )
            self._writes += 1
        return record_id

    @staticmethod
    def _decode_journal(record: ExternalRecord) -> dict[str, Any] | None:
        try:
            value = json.loads(record.content)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(value, dict) or value.get("schema") != JOURNAL_SCHEMA:
            return None
        return value

    @staticmethod
    def _decode_native(record: ExternalRecord, namespace: str) -> CognitiveArtifact | None:
        encoded = record.metadata.get("cogmembench_event")
        if not encoded:
            return None
        try:
            event_data = json.loads(str(encoded))
            event = Event(**event_data)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
        logical_time = int(record.metadata.get("cogmembench_logical_time", event.report_time or 0))
        event_id = event.event_id or f"event:{event.session_id}:{event.turn_id}"
        return CognitiveArtifact(
            artifact_id=f"{event_id}:{record.record_id}",
            kind=ArtifactKind.OBSERVATION,
            content=record.content,
            scenario_id=namespace,
            valid_time=TimeInterval(event.event_time or logical_time),
            transaction_time=TimeInterval(logical_time),
            epistemic_status=EpistemicStatus.ACCEPTED,
            actor_id=event.role,
            session_id=event.session_id,
            turn_id=event.turn_id,
            provenance_event_ids=(event_id,),
            visibility=Visibility.PUBLIC,
        )

    def _records(self) -> list[ExternalRecord]:
        rows = self.store.list_records(self.namespace)
        self._reads += 1
        return rows

    def _journal(self, records: list[ExternalRecord] | None = None) -> list[dict[str, Any]]:
        decoded = [self._decode_journal(row) for row in records or self._records()]
        return sorted(
            (
                row
                for row in decoded
                if row is not None and row.get("namespace") == self.namespace
            ),
            key=lambda row: (int(row["logical_time"]), str(row["record_id"])),
        )

    def _materialize(
        self, records: list[ExternalRecord] | None = None
    ) -> tuple[dict[str, CognitiveArtifact], dict[str, CognitiveRelation], list[dict[str, Any]]]:
        records = records if records is not None else self._records()
        artifacts: dict[str, CognitiveArtifact] = {}
        relations: dict[str, CognitiveRelation] = {}
        retrievals: list[dict[str, Any]] = []
        for row in self._journal(records):
            operation = row["operation"]
            data = row["data"]
            logical_time = int(row["logical_time"])
            if operation == "commit":
                artifact = _artifact_from_dict(data["artifact"])
                artifacts[artifact.artifact_id] = artifact
            elif operation == "revise":
                target_id = str(data["target_id"])
                previous = artifacts.get(target_id)
                if previous is not None and previous.transaction_time is not None:
                    artifacts[target_id] = replace(
                        previous,
                        transaction_time=previous.transaction_time.close(logical_time),
                    )
                revision = _artifact_from_dict(data["revision"])
                artifacts[revision.artifact_id] = revision
                relation = _relation_from_dict(data["relation"])
                relations[relation.relation_id] = relation
            elif operation == "link":
                relation = _relation_from_dict(data["relation"])
                relations[relation.relation_id] = relation
            elif operation == "retrieval":
                retrievals.append(
                    {
                        "logical_time": logical_time,
                        "artifact_ids": tuple(str(item) for item in data["artifact_ids"]),
                    }
                )
        for record in records:
            native = self._decode_native(record, self.namespace)
            if native is not None:
                artifacts[native.artifact_id] = native
        return artifacts, relations, retrievals

    def observe(self, event: Event, logical_time: int) -> CognitiveArtifact:
        self._advance(logical_time)
        if event.report_time is not None and event.report_time != logical_time:
            raise ClockOrderError("event.report_time must match the observe logical_time")
        if not self.native_automatic_capture:
            event_id = event.event_id or f"event:{event.session_id}:{event.turn_id}"
            return self.commit(
                CognitiveArtifact(
                    artifact_id=event_id,
                    kind=ArtifactKind.OBSERVATION,
                    content=event.content,
                    scenario_id=self.namespace,
                    valid_time=TimeInterval(event.event_time or logical_time),
                    epistemic_status=EpistemicStatus.ACCEPTED,
                    actor_id=event.role,
                    session_id=event.session_id,
                    turn_id=event.turn_id,
                    provenance_event_ids=(event_id,),
                    visibility=Visibility.PUBLIC,
                ),
                logical_time,
            )
        event_json = json.dumps(event.to_dict(schema_version=2), sort_keys=True)
        record_id = f"event:{event.event_id or f'{event.session_id}:{event.turn_id}'}"
        metadata = {
            "cogmembench_schema": NATIVE_EVENT_SCHEMA,
            "cogmembench_namespace": self.namespace,
            "cogmembench_record_id": record_id,
            "cogmembench_logical_time": logical_time,
            "cogmembench_event": event_json,
        }
        existing = self.store.list_records(self.namespace)
        self._reads += 1
        stored = next((row for row in existing if row.record_id == record_id), None)
        if stored is None:
            stored = self.store.put_record(
                self.namespace,
                record_id,
                event.content,
                metadata,
                infer=True,
            )
            self._writes += 1
        native = self._decode_native(stored, self.namespace)
        if native is None:
            stored = replace(stored, metadata=metadata)
            native = self._decode_native(stored, self.namespace)
        if native is None:
            raise ValueError("external store did not preserve native-event metadata")
        return native

    def commit(self, artifact: CognitiveArtifact, logical_time: int) -> CognitiveArtifact:
        self._advance(logical_time)
        if artifact.scenario_id != self.namespace:
            raise IsolationError("artifact scenario does not match the active namespace")
        transaction = artifact.transaction_time or TimeInterval(logical_time)
        if transaction.start != logical_time:
            raise ClockOrderError("transaction_time.start must match commit logical_time")
        stored = replace(artifact, transaction_time=transaction)
        artifacts, _, _ = self._materialize()
        existing = artifacts.get(stored.artifact_id)
        if existing is not None:
            if existing == stored:
                return existing
            raise ValueError(f"artifact ID conflict: {stored.artifact_id}")
        self._append("commit", logical_time, {"artifact": _artifact_to_dict(stored)})
        return stored

    def revise(
        self,
        artifact_id: str,
        revision: CognitiveArtifact,
        logical_time: int,
    ) -> CognitiveArtifact:
        self._advance(logical_time)
        artifacts, _, _ = self._materialize()
        previous = artifacts.get(artifact_id)
        if previous is None:
            raise KeyError(artifact_id)
        if previous.transaction_time is None or previous.transaction_time.end is not None:
            existing = artifacts.get(revision.artifact_id)
            if existing is not None:
                return existing
            raise ValueError(f"artifact {artifact_id!r} has already been revised")
        stored = replace(
            revision,
            revision_of=artifact_id,
            transaction_time=revision.transaction_time or TimeInterval(logical_time),
        )
        digest = hashlib.sha256(
            f"{stored.artifact_id}\0supersedes\0{artifact_id}\0{logical_time}".encode()
        ).hexdigest()[:16]
        relation = CognitiveRelation(
            relation_id=f"relation:{digest}",
            source_id=stored.artifact_id,
            kind=RelationKind.SUPERSEDES,
            target_id=artifact_id,
            created_at=logical_time,
            source=f"{self.store.store_name}-mapped-journal",
        )
        self._append(
            "revise",
            logical_time,
            {
                "target_id": artifact_id,
                "revision": _artifact_to_dict(stored),
                "relation": _relation_to_dict(relation),
            },
        )
        return stored

    def link(
        self,
        source_id: str,
        relation: RelationKind,
        target_id: str,
        logical_time: int,
        *,
        strength: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CognitiveRelation:
        self._advance(logical_time)
        artifacts, relations, _ = self._materialize()
        if source_id not in artifacts or target_id not in artifacts:
            missing = source_id if source_id not in artifacts else target_id
            raise KeyError(missing)
        digest = hashlib.sha256(
            f"{source_id}\0{relation.value}\0{target_id}\0{logical_time}".encode()
        ).hexdigest()[:16]
        row = CognitiveRelation(
            relation_id=f"relation:{digest}",
            source_id=source_id,
            kind=relation,
            target_id=target_id,
            created_at=logical_time,
            strength=strength,
            source=f"{self.store.store_name}-mapped-journal",
            metadata=metadata or {},
        )
        existing = relations.get(row.relation_id)
        if existing is not None:
            return existing
        self._append("link", logical_time, {"relation": _relation_to_dict(row)})
        return row

    @staticmethod
    def _visible(
        artifacts: dict[str, CognitiveArtifact],
        knowledge_time: int,
        valid_at: int | None,
    ) -> dict[str, CognitiveArtifact]:
        return {
            artifact_id: artifact
            for artifact_id, artifact in artifacts.items()
            if artifact.transaction_time is not None
            and artifact.transaction_time.contains(knowledge_time)
            and (valid_at is None or artifact.valid_time.contains(valid_at))
        }

    def retrieve(
        self,
        query: str,
        budget: RetrievalBudget,
        logical_time: int,
        valid_at: int | None = None,
        known_at: int | None = None,
    ) -> RetrievalResult:
        self._advance(logical_time)
        limit = min(max(budget.max_items * 4, budget.max_items), self.store.max_search_results)
        searched = self.store.search_records(self.namespace, query, limit)
        all_records = self._records()
        artifacts, _, _ = self._materialize(all_records)
        knowledge_time = self._last_logical_time if known_at is None else known_at
        visible = self._visible(artifacts, knowledge_time, valid_at)
        scores: dict[str, float] = {}
        for record in searched:
            journal = self._decode_journal(record)
            candidate_ids: list[str] = []
            if journal is not None:
                data = journal["data"]
                if journal["operation"] == "commit":
                    candidate_ids.append(str(data["artifact"]["artifact_id"]))
                elif journal["operation"] == "revise":
                    candidate_ids.extend(
                        (str(data["target_id"]), str(data["revision"]["artifact_id"]))
                    )
            native = self._decode_native(record, self.namespace)
            if native is not None:
                visible[native.artifact_id] = native
                candidate_ids.append(native.artifact_id)
            for artifact_id in candidate_ids:
                if artifact_id in visible:
                    scores[artifact_id] = max(scores.get(artifact_id, 0.0), float(record.score))
        ranked = sorted(
            (RetrievedArtifact(visible[artifact_id], score) for artifact_id, score in scores.items()),
            key=lambda item: (-item.score, item.artifact.artifact_id),
        )
        selected: list[RetrievedArtifact] = []
        chars = 0
        tokens = 0
        for item in ranked:
            content = item.artifact.content
            next_chars = chars + len(content)
            next_tokens = tokens + len(WORD.findall(content.lower()))
            if len(selected) >= budget.max_items:
                break
            if budget.max_context_chars is not None and next_chars > budget.max_context_chars:
                continue
            if budget.max_context_tokens is not None and next_tokens > budget.max_context_tokens:
                continue
            selected.append(item)
            chars = next_chars
            tokens = next_tokens
        self._reads += 1
        self._append(
            "retrieval",
            logical_time,
            {"query": query, "artifact_ids": [item.artifact.artifact_id for item in selected]},
        )
        return RetrievalResult(
            query=query,
            logical_time=logical_time,
            items=tuple(selected),
            truncated=len(selected) < len(ranked),
        )

    def snapshot(
        self,
        valid_at: int | None = None,
        known_at: int | None = None,
    ) -> SnapshotResult:
        records = self._records()
        artifacts, relations, _ = self._materialize(records)
        knowledge_time = self._last_logical_time if known_at is None else known_at
        visible = self._visible(artifacts, knowledge_time, valid_at)
        visible_relations = tuple(
            sorted(
                (
                    relation
                    for relation in relations.values()
                    if relation.created_at <= knowledge_time
                    and (valid_at is None or relation.valid_time is None or relation.valid_time.contains(valid_at))
                ),
                key=lambda row: row.relation_id,
            )
        )
        payload = {
            "namespace": self.namespace,
            "valid_at": valid_at,
            "known_at": knowledge_time,
            "artifact_ids": sorted(visible),
            "relation_ids": [row.relation_id for row in visible_relations],
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
        return SnapshotResult(
            f"snapshot:{digest}",
            valid_at,
            knowledge_time,
            tuple(visible[key] for key in sorted(visible)),
            visible_relations,
        )

    def export_audit(self, decision_ref: str) -> AuditReceipt:
        if not self.audit_export_enabled:
            from .adapter import UnsupportedCapabilityError

            raise UnsupportedCapabilityError("adapter does not export audit receipts")
        artifacts, relations, retrievals = self._materialize()
        decision = artifacts.get(decision_ref)
        if decision is None:
            raise KeyError(decision_ref)
        if decision.kind is not ArtifactKind.DECISION or decision.transaction_time is None:
            raise ValueError("audit target must be a timestamped decision")
        decision_time = decision.transaction_time.start
        supporting = [
            row
            for row in relations.values()
            if row.target_id == decision_ref and row.created_at <= decision_time
        ]
        claimed = tuple(
            str(item) for item in decision.structured_content.get("retrieved_artifact_ids", ())
        )
        observed = {
            artifact_id
            for retrieval in retrievals
            if retrieval["logical_time"] <= decision_time
            for artifact_id in retrieval["artifact_ids"]
        }
        retrieved = tuple(item for item in claimed if item in observed)
        return AuditReceipt(
            decision_ref=decision_ref,
            decision_time=decision_time,
            evidence_ids=tuple(
                sorted(row.source_id for row in supporting if row.kind is RelationKind.SUPPORTS)
            ),
            intermediate_artifact_ids=tuple(
                sorted(
                    row.source_id
                    for row in supporting
                    if row.kind in {RelationKind.DERIVED_FROM, RelationKind.DEPENDS_ON}
                )
            ),
            source_event_ids=decision.provenance_event_ids,
            retrieved_artifact_ids=retrieved,
            retrieval_times=tuple(
                retrieval["logical_time"]
                for retrieval in retrievals
                if set(retrieval["artifact_ids"]) & set(retrieved)
                and retrieval["logical_time"] <= decision_time
            ),
            assumptions=tuple(decision.structured_content.get("assumptions", ())),
            alternatives=tuple(decision.structured_content.get("alternatives", ())),
        )

    def usage_report(self) -> UsageReport:
        return UsageReport(
            fidelity=UsageFidelity.LOWER_BOUND,
            read_operations=self._reads,
            write_operations=self._writes,
            reason="external substrate-internal model, embedding, and storage usage is unavailable",
            metadata={"store": self.store.store_name},
        )

    def capability_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            adapter_name=self.store.store_name,
            adapter_version=self.store.store_version,
            clock_mode=ClockMode.MAPPED,
            snapshot=True,
            branching=False,
            audit_export=self.audit_export_enabled,
            agent_directed_capture=True,
            oracle_capture=True,
            usage_fidelity=UsageFidelity.LOWER_BOUND,
            asynchronous_ingestion=self.store.asynchronous,
            max_context_items=self.store.max_search_results,
            notes=(
                "canonical operations are persisted as a remote append-only journal",
                "logical time is adapter-mapped; vendor-native temporal semantics are reported separately",
                "no harness-only state is used for evaluation",
            ),
            evidence_mode=EvidenceMode.MAPPED,
            automatic_capture=self.native_automatic_capture,
            revision=True,
            relations=True,
        )
